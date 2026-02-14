import os
import subprocess
import sys
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
MEDIA_DIR = 'media'
OUTPUT_DIR = 'media_compressed'
VIDEO_EXTS = {'.mp4', '.mov', '.webm', '.ogg', '.avi', '.mkv', '.flv'}

# Number of parallel encodes (NVENC supports 3-5 simultaneous sessions)
MAX_PARALLEL = 3

# FFmpeg GPU encoding settings (NVIDIA NVENC - RTX 5070 Ti)
GPU_SETTINGS = {
    'resolution': '1920',        # Max width (auto height, no upscale)
    'fps': 60,                   # Target framerate
    'codec': 'h264_nvenc',       # NVIDIA GPU encoder
    'preset': 'p5',              # NVENC preset: p1(fastest)..p7(best quality), p5=good balance
    'tune': 'hq',                # Tuning: hq = high quality
    'rc': 'vbr',                 # Rate control: variable bitrate
    'cq': 22,                    # Constant quality level (like CRF, lower=better, 18-24 good range)
    'b_v': '8M',                 # Target video bitrate
    'maxrate': '12M',            # Max video bitrate (for peaks)
    'bufsize': '16M',            # Buffer size
    'audio_bitrate': '192k',     # Audio bitrate
    'audio_codec': 'aac',        # Audio codec
    'pixel_format': 'yuv420p',   # Pixel format
}

# Fallback CPU settings (if GPU fails)
CPU_SETTINGS = {
    'resolution': '1920',
    'fps': 60,
    'codec': 'libx264',
    'crf': 20,
    'preset': 'medium',          # Faster than 'slow' for CPU fallback
    'audio_bitrate': '192k',
    'audio_codec': 'aac',
    'pixel_format': 'yuv420p',
}


def check_ffmpeg():
    """Verify FFmpeg is installed."""
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                                capture_output=True, text=True, timeout=5)
        version_line = result.stdout.split('\n')[0]
        print(f"  ✅ FFmpeg: {version_line}")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  ❌ FFmpeg not found! Install: winget install ffmpeg")
        return False


def check_nvenc():
    """Test if NVENC actually works by doing a tiny encode."""
    import tempfile
    test_output = os.path.join(tempfile.gettempdir(), '_nvenc_test.mp4')
    try:
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1:r=30',
            '-c:v', 'h264_nvenc', '-preset', 'p1',
            test_output
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        # Check if output file was created (most reliable check)
        if os.path.exists(test_output) and os.path.getsize(test_output) > 0:
            os.remove(test_output)
            print("  ✅ NVENC: NVIDIA GPU encoding ready (RTX 5070 Ti)")
            return True
        # Fallback: check if encoder was initialized in stderr
        if 'h264_nvenc' in result.stderr and result.returncode == 0:
            print("  ✅ NVENC: NVIDIA GPU encoding ready")
            return True
    except Exception:
        pass
    finally:
        if os.path.exists(test_output):
            try: os.remove(test_output)
            except: pass
    print("  ⚠️  NVENC unavailable, falling back to CPU encoding")
    return False


def get_video_info(filepath):
    """Get video metadata using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)

        video_stream = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break

        duration = float(data.get('format', {}).get('duration', 0))
        size = int(data.get('format', {}).get('size', 0))
        width = int(video_stream.get('width', 0)) if video_stream else 0
        height = int(video_stream.get('height', 0)) if video_stream else 0

        fps_str = video_stream.get('r_frame_rate', '0/1') if video_stream else '0/1'
        try:
            num, den = fps_str.split('/')
            fps = round(int(num) / int(den), 2)
        except:
            fps = 0

        return {'duration': duration, 'size': size, 'width': width, 'height': height, 'fps': fps}
    except:
        return {'duration': 0, 'size': 0, 'width': 0, 'height': 0, 'fps': 0}


def format_size(size_bytes):
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_duration(seconds):
    """Human-readable duration."""
    mins, secs = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs}h {mins}m {secs}s"
    return f"{mins}m {secs}s"


def build_gpu_cmd(input_path, output_path):
    """Build FFmpeg command for NVENC GPU encoding."""
    s = GPU_SETTINGS
    # Cap to FHD 1920x1080 max (no upscaling, keep aspect ratio, divisible by 2)
    scale_filter = (
        "scale='min(iw,1920)':'min(ih,1080)':force_original_aspect_ratio=decrease,"
        "pad='ceil(iw/2)*2':'ceil(ih/2)*2'"
    )

    return [
        'ffmpeg', '-y',
        '-hwaccel', 'cuda',                 # GPU-accelerated decoding
        '-i', input_path,
        '-c:v', s['codec'],                  # h264_nvenc
        '-preset', s['preset'],              # p5 (quality/speed balance)
        '-tune', s['tune'],                  # hq
        '-rc', s['rc'],                      # vbr
        '-cq', str(s['cq']),                 # Constant quality
        '-b:v', s['b_v'],                    # Target bitrate
        '-maxrate', s['maxrate'],            # Max bitrate
        '-bufsize', s['bufsize'],            # Buffer
        '-r', str(s['fps']),                 # Framerate
        '-vf', scale_filter,                 # Scale filter
        '-pix_fmt', s['pixel_format'],
        '-c:a', s['audio_codec'],
        '-b:a', s['audio_bitrate'],
        '-movflags', '+faststart',           # Web streaming optimization
        output_path
    ]


def build_cpu_cmd(input_path, output_path):
    """Build FFmpeg command for CPU fallback encoding."""
    s = CPU_SETTINGS
    # Cap to FHD 1920x1080 max (no upscaling, keep aspect ratio, divisible by 2)
    scale_filter = (
        "scale='min(iw,1920)':'min(ih,1080)':force_original_aspect_ratio=decrease,"
        "pad='ceil(iw/2)*2':'ceil(ih/2)*2'"
    )

    return [
        'ffmpeg', '-y',
        '-i', input_path,
        '-c:v', s['codec'],
        '-preset', s['preset'],
        '-crf', str(s['crf']),
        '-r', str(s['fps']),
        '-vf', scale_filter,
        '-pix_fmt', s['pixel_format'],
        '-c:a', s['audio_codec'],
        '-b:a', s['audio_bitrate'],
        '-movflags', '+faststart',
        '-threads', '0',
        output_path
    ]


def compress_video(input_path, output_path, index, total, use_gpu=True):
    """Compress a single video. Returns (success, filename, original_size, compressed_size, elapsed)."""
    filename = os.path.basename(input_path)
    original_size = os.path.getsize(input_path)
    info = get_video_info(input_path)

    label = f"[{index}/{total}]"
    mode = "🟢 GPU" if use_gpu else "🔵 CPU"
    print(f"  {label} {mode} ⏳ {filename} "
          f"({info['width']}x{info['height']} @ {info['fps']}fps, {format_size(original_size)})")

    # Build command
    if use_gpu:
        cmd = build_gpu_cmd(input_path, output_path)
    else:
        cmd = build_cpu_cmd(input_path, output_path)

    start_time = time.time()

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True
        )
        _, stderr = process.communicate()
        elapsed = time.time() - start_time

        # If GPU fails, retry with CPU
        if process.returncode != 0 and use_gpu:
            print(f"  {label} ⚠️  GPU failed for {filename}, retrying with CPU...")
            cmd = build_cpu_cmd(input_path, output_path)
            start_time = time.time()
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True
            )
            _, stderr = process.communicate()
            elapsed = time.time() - start_time
            mode = "🔵 CPU"

        if process.returncode != 0:
            error_lines = stderr.strip().split('\n')[-2:]
            print(f"  {label} ❌ FAILED: {filename}")
            for line in error_lines:
                print(f"       {line.strip()}")
            return (False, filename, original_size, 0, elapsed)

        compressed_size = os.path.getsize(output_path)
        savings = original_size - compressed_size
        savings_pct = (savings / original_size * 100) if original_size > 0 else 0

        if savings > 0:
            print(f"  {label} ✅ {filename}: {format_size(original_size)} → "
                  f"{format_size(compressed_size)} (-{savings_pct:.1f}%) "
                  f"[{elapsed:.1f}s]")
        else:
            print(f"  {label} ⚠️  {filename}: already optimal "
                  f"({format_size(original_size)} → {format_size(compressed_size)}) "
                  f"[{elapsed:.1f}s]")

        return (True, filename, original_size, compressed_size, elapsed)

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  {label} ❌ {filename}: {e}")
        return (False, filename, original_size, 0, elapsed)


def main():
    print("\n" + "=" * 60)
    print("  🎬 SOSE '26 Video Compressor")
    print("  GPU Accelerated • HD 60fps • Parallel Processing")
    print("=" * 60 + "\n")

    # System checks
    if not check_ffmpeg():
        sys.exit(1)

    use_gpu = check_nvenc()

    # Check media directory
    if not os.path.exists(MEDIA_DIR):
        print(f"\n❌ Media directory '{MEDIA_DIR}' not found!")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Find all videos
    videos = []
    for f in sorted(os.listdir(MEDIA_DIR)):
        if f.startswith('.'):
            continue
        _, ext = os.path.splitext(f)
        if ext.lower() in VIDEO_EXTS:
            videos.append(f)

    if not videos:
        print(f"\n📭 No videos found in '{MEDIA_DIR}/'")
        sys.exit(0)

    total_original = sum(os.path.getsize(os.path.join(MEDIA_DIR, v)) for v in videos)
    parallel = MAX_PARALLEL if use_gpu else 1  # CPU: sequential, GPU: parallel

    print(f"\n📂 Found {len(videos)} videos ({format_size(total_original)})")
    print(f"📁 Output: {OUTPUT_DIR}/")

    if use_gpu:
        s = GPU_SETTINGS
        print(f"\n⚙️  GPU Settings (NVENC):")
        print(f"   Encoder:    {s['codec']} (preset {s['preset']}, tune {s['tune']})")
        print(f"   Quality:    CQ {s['cq']} | VBR {s['b_v']} (max {s['maxrate']})")
        print(f"   Resolution: ≤{s['resolution']}p @ {s['fps']}fps")
        print(f"   Parallel:   {parallel} simultaneous encodes")
    else:
        s = CPU_SETTINGS
        print(f"\n⚙️  CPU Settings:")
        print(f"   Encoder:    {s['codec']} (preset {s['preset']})")
        print(f"   Quality:    CRF {s['crf']}")
        print(f"   Resolution: ≤{s['resolution']}p @ {s['fps']}fps")

    print(f"\n{'─'*60}")
    print(f"  Starting compression...")
    print(f"{'─'*60}")

    global_start = time.time()
    results = []

    # Build task list
    tasks = []
    for i, filename in enumerate(videos, 1):
        input_path = os.path.join(MEDIA_DIR, filename)
        output_name = Path(filename).stem + '.mp4'
        output_path = os.path.join(OUTPUT_DIR, output_name)
        tasks.append((input_path, output_path, i, len(videos)))

    # Parallel execution with ThreadPool
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {
            executor.submit(
                compress_video, inp, out, idx, total, use_gpu
            ): idx
            for inp, out, idx, total in tasks
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    global_elapsed = time.time() - global_start

    # Final summary
    success = [r for r in results if r[0]]
    failed = [r for r in results if not r[0]]
    total_compressed = sum(r[3] for r in success)
    total_orig = sum(r[2] for r in results)
    total_saved = total_orig - total_compressed
    saved_pct = (total_saved / total_orig * 100) if total_orig > 0 else 0

    print(f"\n{'='*60}")
    print(f"  📊 COMPRESSION SUMMARY")
    print(f"{'='*60}")
    print(f"  Mode:       {'🟢 GPU (NVENC)' if use_gpu else '🔵 CPU (x264)'}")
    print(f"  Parallel:   {parallel} workers")
    print(f"  ✅ Success:  {len(success)}/{len(videos)}")
    if failed:
        print(f"  ❌ Failed:   {len(failed)}")
        for r in failed:
            print(f"     • {r[1]}")
    print(f"  📦 Original:   {format_size(total_orig)}")
    print(f"  📦 Compressed: {format_size(total_compressed)}")
    print(f"  💾 Saved:      {format_size(total_saved)} (-{saved_pct:.1f}%)")
    print(f"  ⏱️  Total time: {format_duration(global_elapsed)}")
    print(f"  📁 Output:     {OUTPUT_DIR}/")
    print(f"{'='*60}")
    print(f"\n💡 Compressed files in '{OUTPUT_DIR}/'.")


if __name__ == '__main__':
    main()
