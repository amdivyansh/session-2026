import os
import json
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, jsonify

app = Flask(__name__)

# --- CONFIGURATION ---
MEDIA_DIR = 'media'
DATA_FILE = 'media.json'
STUDENT_FILE = 'student.json'
DEFAULT_TITLE = "Farewell Party"
DEFAULT_DATE = "SOSE '26"

# GitHub LFS URI Configuration
GITHUB_USERNAME = 'amdivyansh'
GITHUB_REPO = 'session-2026'
GITHUB_BRANCH = 'refs/heads/main'
GITHUB_LFS_BASE = f'https://media.githubusercontent.com/media/{GITHUB_USERNAME}/{GITHUB_REPO}/{GITHUB_BRANCH}'

# Supported Extensions
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.webm', '.ogg'}

# --- HTML TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gallery Manager</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: sans-serif; }
        .input-field { background: #1e293b; border: 1px solid #334155; color: white; padding: 0.75rem; border-radius: 0.5rem; width: 100%; margin-bottom: 1rem; outline: none; transition: border-color 0.2s; }
        .input-field:focus { border-color: #3b82f6; }
        .btn { padding: 0.5rem 1rem; border-radius: 0.5rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-success { background: #22c55e; color: white; width: 100%; padding: 0.75rem; }
        .btn-success:hover { background: #16a34a; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; overflow: hidden; }
        .preview-media { max-height: 400px; width: 100%; object-fit: contain; border-radius: 0.5rem; background: #000; }

        /* Student Tag Selector */
        .tag-selector { position: relative; }
        .tag-search-input {
            background: #1e293b; border: 1px solid #334155; color: white;
            padding: 0.6rem 0.75rem; border-radius: 0.5rem; width: 100%;
            outline: none; transition: border-color 0.2s; font-size: 0.875rem;
        }
        .tag-search-input:focus { border-color: #8b5cf6; }
        .tag-search-input::placeholder { color: #64748b; }

        .student-dropdown {
            position: absolute; top: 100%; left: 0; right: 0; z-index: 50;
            background: #1e293b; border: 1px solid #475569; border-radius: 0.5rem;
            max-height: 240px; overflow-y: auto; margin-top: 4px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            display: none;
        }
        .student-dropdown.open { display: block; }

        .student-dropdown::-webkit-scrollbar { width: 4px; }
        .student-dropdown::-webkit-scrollbar-track { background: transparent; }
        .student-dropdown::-webkit-scrollbar-thumb { background: #6366f1; border-radius: 2px; }

        .student-option {
            display: flex; align-items: center; gap: 10px;
            padding: 8px 12px; cursor: pointer; transition: background 0.15s;
            font-size: 0.85rem; border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        .student-option:hover { background: rgba(99, 102, 241, 0.15); }
        .student-option.selected { background: rgba(99, 102, 241, 0.2); }

        .student-option .check-box {
            width: 18px; height: 18px; border-radius: 4px;
            border: 2px solid #475569; display: flex; align-items: center;
            justify-content: center; flex-shrink: 0; transition: all 0.15s;
        }
        .student-option.selected .check-box {
            background: #6366f1; border-color: #6366f1;
        }
        .student-option .check-box svg {
            width: 12px; height: 12px; color: white;
            opacity: 0; transition: opacity 0.15s;
        }
        .student-option.selected .check-box svg { opacity: 1; }

        .tag-chips-area {
            display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; min-height: 28px;
        }
        .tag-chip {
            display: inline-flex; align-items: center; gap: 4px;
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(139, 92, 246, 0.2));
            border: 1px solid rgba(99, 102, 241, 0.4);
            color: #c4b5fd; padding: 3px 10px; border-radius: 20px;
            font-size: 0.75rem; font-weight: 600; cursor: default;
            animation: chipIn 0.2s ease-out;
        }
        .tag-chip .remove-chip {
            cursor: pointer; margin-left: 2px; opacity: 0.6;
            transition: opacity 0.15s; font-size: 14px; line-height: 1;
        }
        .tag-chip .remove-chip:hover { opacity: 1; color: #f87171; }

        @keyframes chipIn {
            from { transform: scale(0.8); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }

        .no-match {
            padding: 16px; text-align: center; color: #64748b; font-size: 0.8rem;
        }

        .student-count-badge {
            position: absolute; top: -6px; right: -6px;
            background: #6366f1; color: white; font-size: 10px;
            font-weight: 700; min-width: 18px; height: 18px;
            border-radius: 9px; display: flex; align-items: center;
            justify-content: center; padding: 0 5px;
        }
    </style>
</head>
<body class="p-4 md:p-8 max-w-7xl mx-auto">

    <header class="flex flex-col md:flex-row justify-between items-center mb-10 border-b border-gray-700 pb-6">
        <div>
            <h1 class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">Gallery Admin</h1>
            <p class="text-gray-400 text-sm mt-1">Manage your Farewell memories</p>
        </div>
        <div class="flex items-center gap-4 mt-4 md:mt-0">
            <div class="text-xs text-gray-500 font-mono bg-gray-900 px-4 py-2 rounded">
                GitHub LFS: <span class="text-indigo-400">{{ github_base }}</span>
            </div>
        </div>
    </header>

    {% if mode == 'list' %}
        <div class="mb-12">
            <div class="flex justify-between items-end mb-6">
                <h2 class="text-xl font-semibold text-white">Untracked Media <span class="text-gray-500 text-sm ml-2">({{ files|length }} found)</span></h2>
            </div>

            {% if files|length == 0 %}
                <div class="flex flex-col items-center justify-center p-12 bg-gray-800/50 border border-gray-700 rounded-xl text-center">
                    <div class="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mb-4">
                        <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                    </div>
                    <h3 class="text-lg font-medium text-white">All Caught Up!</h3>
                    <p class="text-gray-400 mt-2">All files in the media folder are already in your JSON database.</p>
                </div>
            {% else %}
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                    {% for file in files %}
                    <div class="card group hover:border-blue-500/50 transition-colors">
                        <div class="h-48 bg-black relative group">
                            {% if file.type == 'image' %}
                                <img src="{{ url_for('serve_media', filename=file.name) }}" class="object-cover w-full h-full opacity-80 group-hover:opacity-100 transition-opacity">
                            {% else %}
                                <video src="{{ url_for('serve_media', filename=file.name) }}" class="object-cover w-full h-full opacity-80"></video>
                                <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
                                    <div class="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
                                        <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                                    </div>
                                </div>
                            {% endif %}
                            <div class="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/80 to-transparent">
                                <span class="text-xs font-mono text-gray-300 truncate block">{{ file.name }}</span>
                            </div>
                        </div>
                        <div class="p-4">
                            <a href="{{ url_for('edit_media', filename=file.name) }}" class="btn btn-primary w-full block text-center text-sm">Add to Gallery</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            {% endif %}
        </div>

        <div class="border-t border-gray-700 pt-8">
            <details class="group">
                <summary class="flex items-center cursor-pointer list-none text-gray-500 hover:text-white mb-4">
                    <span class="text-sm font-semibold uppercase tracking-wider">View Raw JSON Data</span>
                    <svg class="w-4 h-4 ml-2 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                </summary>
                <pre class="bg-gray-900 p-4 rounded-lg text-xs text-gray-400 overflow-auto max-h-96 font-mono border border-gray-800">{{ current_json }}</pre>
            </details>
        </div>

    {% elif mode == 'edit' %}
        <div class="max-w-4xl mx-auto">
            <a href="{{ url_for('index') }}" class="inline-flex items-center text-gray-400 hover:text-white mb-6 transition-colors">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                Back to List
            </a>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <!-- Preview Side -->
                <div class="order-2 lg:order-1">
                    <div class="bg-black rounded-xl overflow-hidden shadow-2xl border border-gray-700 sticky top-8">
                        {% if file_type == 'image' %}
                            <img src="{{ url_for('serve_media', filename=filename) }}" class="preview-media">
                        {% else %}
                            <video controls src="{{ url_for('serve_media', filename=filename) }}" class="preview-media"></video>
                        {% endif %}
                        <div class="p-4 bg-gray-900 border-t border-gray-800">
                            <p class="font-mono text-xs text-gray-500">File: {{ filename }}</p>
                            <p class="font-mono text-xs text-gray-500 mt-1">Type: {{ file_type|upper }}</p>
                            <p class="font-mono text-xs text-indigo-400 mt-1 break-all">LFS: {{ lfs_uri }}</p>
                        </div>
                    </div>
                </div>

                <!-- Form Side -->
                <div class="order-1 lg:order-2">
                    <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-xl">
                        <h2 class="text-xl font-bold text-white mb-6">Add Media Details</h2>

                        <form action="{{ url_for('save_media') }}" method="POST" id="media-form">
                            <input type="hidden" name="filename" value="{{ filename }}">
                            <input type="hidden" name="file_type" value="{{ file_type }}">
                            <input type="hidden" name="student_tags" id="student-tags-hidden" value="">

                            <div class="mb-4">
                                <label class="block text-xs uppercase text-gray-500 font-bold mb-2">Title / Headline</label>
                                <input type="text" name="title" class="input-field text-lg font-semibold" value="{{ default_title }}" required autofocus>
                            </div>

                            <div class="mb-4">
                                <label class="block text-xs uppercase text-gray-500 font-bold mb-2">Date / Event</label>
                                <input type="text" name="date" class="input-field" value="{{ default_date }}">
                            </div>

                            <!-- Student Tags Multi-Select -->
                            <div class="mb-4">
                                <label class="block text-xs uppercase text-gray-500 font-bold mb-2">
                                    Student Tags
                                    <span class="text-indigo-400 normal-case font-normal">(click to select)</span>
                                </label>
                                <div class="tag-selector" id="tag-selector">
                                    <div class="relative">
                                        <input type="text" class="tag-search-input" id="student-search"
                                            placeholder="🔍 Search students..." autocomplete="off"
                                            onfocus="openStudentDropdown()" oninput="filterStudents(this.value)">
                                    </div>
                                    <div class="student-dropdown" id="student-dropdown">
                                        {% for student in students %}
                                        <div class="student-option" data-tag="{{ student.tag }}" data-name="{{ student.name }}" onclick="toggleStudentTag(this)">
                                            <div class="check-box">
                                                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
                                            </div>
                                            <span>{{ student.name }}</span>
                                            <span style="margin-left:auto; color:#64748b; font-size:0.7rem;">{{ student.tag }}</span>
                                        </div>
                                        {% endfor %}
                                        <div class="no-match" id="no-match" style="display:none;">No students found</div>
                                    </div>
                                    <div class="tag-chips-area" id="tag-chips">
                                        <!-- Chips rendered by JS -->
                                    </div>
                                </div>
                            </div>

                            <!-- Additional custom tags -->
                            <div class="mb-4">
                                <label class="block text-xs uppercase text-gray-500 font-bold mb-2">Extra Tags <span class="text-gray-600 normal-case font-normal">(comma separated)</span></label>
                                <input type="text" name="extra_tags" class="input-field" placeholder="dance, stage, group photo">
                            </div>

                            <div class="mb-6">
                                <label class="block text-xs uppercase text-gray-500 font-bold mb-2">Description / Memory</label>
                                <textarea name="description" class="input-field h-24 resize-none leading-relaxed" placeholder="Write something about this moment..."></textarea>
                            </div>

                            <button type="submit" class="btn btn-success shadow-lg shadow-green-500/20 flex items-center justify-center gap-2">
                                <span>Save & Next</span>
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // --- Student Tag Multi-Select Logic ---
            const selectedTags = new Set();

            function openStudentDropdown() {
                document.getElementById('student-dropdown').classList.add('open');
            }

            function closeStudentDropdown() {
                document.getElementById('student-dropdown').classList.remove('open');
            }

            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                const selector = document.getElementById('tag-selector');
                if (selector && !selector.contains(e.target)) {
                    closeStudentDropdown();
                }
            });

            function filterStudents(query) {
                const dropdown = document.getElementById('student-dropdown');
                const options = dropdown.querySelectorAll('.student-option');
                const noMatch = document.getElementById('no-match');
                const q = query.toLowerCase().trim();
                let visibleCount = 0;

                options.forEach(opt => {
                    const name = opt.dataset.name.toLowerCase();
                    const tag = opt.dataset.tag.toLowerCase();
                    if (name.includes(q) || tag.includes(q)) {
                        opt.style.display = '';
                        visibleCount++;
                    } else {
                        opt.style.display = 'none';
                    }
                });

                noMatch.style.display = visibleCount === 0 ? '' : 'none';
                openStudentDropdown();
            }

            function toggleStudentTag(el) {
                const tag = el.dataset.tag;
                if (selectedTags.has(tag)) {
                    selectedTags.delete(tag);
                    el.classList.remove('selected');
                } else {
                    selectedTags.add(tag);
                    el.classList.add('selected');
                }
                renderChips();
                syncHiddenField();
            }

            function removeTag(tag) {
                selectedTags.delete(tag);
                // Update option visual
                document.querySelectorAll('.student-option').forEach(opt => {
                    if (opt.dataset.tag === tag) opt.classList.remove('selected');
                });
                renderChips();
                syncHiddenField();
            }

            function renderChips() {
                const container = document.getElementById('tag-chips');
                container.innerHTML = '';
                selectedTags.forEach(tag => {
                    const chip = document.createElement('span');
                    chip.className = 'tag-chip';
                    chip.innerHTML = `${tag} <span class="remove-chip" onclick="event.stopPropagation(); removeTag('${tag}')">&times;</span>`;
                    container.appendChild(chip);
                });
            }

            function syncHiddenField() {
                document.getElementById('student-tags-hidden').value = JSON.stringify(Array.from(selectedTags));
            }
        </script>
    {% endif %}

</body>
</html>
"""

# --- HELPERS ---

def load_students():
    """Load student list from student.json."""
    if not os.path.exists(STUDENT_FILE):
        return []
    try:
        with open(STUDENT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def make_lfs_uri(filename):
    """Construct GitHub LFS URI for a media file."""
    return f"{GITHUB_LFS_BASE}/{MEDIA_DIR}/{filename}"

def load_data():
    """Read the JSON file and return list."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_entry(entry):
    """Append entry to JSON file."""
    data = load_data()

    # Calculate unique ID
    next_id = 1
    if data:
        next_id = max(item['id'] for item in data) + 1

    entry['id'] = next_id
    data.append(entry)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_untracked_files():
    """Scan folder and exclude files already in JSON."""
    if not os.path.exists(MEDIA_DIR):
        os.makedirs(MEDIA_DIR)

    all_files = os.listdir(MEDIA_DIR)

    current_data = load_data()
    tracked_files = set()
    for item in current_data:
        if 'src' in item:
            # Extract filename from either local path or LFS URI
            tracked_files.add(os.path.basename(item['src']))

    untracked = []
    for f in sorted(all_files):
        if f.startswith('.'): continue
        if f in tracked_files: continue

        _, ext = os.path.splitext(f)
        if ext.lower() in IMAGE_EXTS:
            untracked.append({'name': f, 'type': 'image'})
        elif ext.lower() in VIDEO_EXTS:
            untracked.append({'name': f, 'type': 'video'})

    return untracked

# --- FLASK ROUTES ---

@app.route('/')
def index():
    files = get_untracked_files()
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            current_json = f.read()
    except:
        current_json = "[]"

    return render_template_string(HTML_TEMPLATE,
                                mode='list',
                                files=files,
                                current_json=current_json,
                                media_dir=MEDIA_DIR,
                                json_file=DATA_FILE,
                                github_base=GITHUB_LFS_BASE)

@app.route('/media/<path:filename>')
def serve_media(filename):
    """Serve the actual image/video file so the browser can see it."""
    return send_from_directory(MEDIA_DIR, filename)

@app.route('/add/<filename>')
def edit_media(filename):
    """Show the form to edit details with student tag selector."""
    _, ext = os.path.splitext(filename)
    file_type = 'image' if ext.lower() in IMAGE_EXTS else 'video'
    students = load_students()
    lfs_uri = make_lfs_uri(filename)

    return render_template_string(HTML_TEMPLATE,
                                mode='edit',
                                filename=filename,
                                file_type=file_type,
                                default_title=DEFAULT_TITLE,
                                default_date=DEFAULT_DATE,
                                students=students,
                                lfs_uri=lfs_uri,
                                github_base=GITHUB_LFS_BASE)

@app.route('/save', methods=['POST'])
def save_media():
    """Process form and save to JSON with GitHub LFS URIs."""
    filename = request.form.get('filename')
    file_type = request.form.get('file_type')
    title = request.form.get('title')
    date = request.form.get('date')
    desc = request.form.get('description', '')

    # Process student tags (JSON array from hidden field)
    student_tags_raw = request.form.get('student_tags', '[]')
    try:
        student_tags = json.loads(student_tags_raw)
    except json.JSONDecodeError:
        student_tags = []

    # Process extra tags (comma separated)
    extra_tags_input = request.form.get('extra_tags', '')
    extra_tags = [t.strip() for t in extra_tags_input.split(',') if t.strip()]

    # Combine all tags
    all_tags = student_tags + extra_tags

    # Build GitHub LFS URI
    lfs_uri = make_lfs_uri(filename)

    # Construct the entry with LFS URIs
    entry = {
        "id": 0,  # Placeholder, set in save_entry
        "type": file_type,
        "src": lfs_uri,
        "title": title,
        "description": desc,
        "date": date,
        "tags": all_tags
    }

    if file_type == 'video':
        entry["thumbnail"] = lfs_uri

    save_entry(entry)

    # Auto-advance to next untracked file
    remaining = get_untracked_files()
    if remaining:
        return redirect(url_for('edit_media', filename=remaining[0]['name']))

    return redirect(url_for('index'))

if __name__ == '__main__':
    print(f"🚀 Gallery Admin running on http://127.0.0.1:5000")
    print(f"📂 Scanning folder: {MEDIA_DIR}")
    print(f"💾 Saving to: {DATA_FILE}")
    print(f"🔗 GitHub LFS base: {GITHUB_LFS_BASE}")
    app.run(debug=True, port=5000)