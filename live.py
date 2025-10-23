#!/usr/bin/env python3
"""ASTERISK - Minimal HLS Stream Server"""

import sys
import subprocess
import shutil
from pathlib import Path

def check_and_install_python_packages():
    required_packages = {
        'aiohttp': 'aiohttp',
        'aiohttp_cors': 'aiohttp-cors'
    }
    
    print("🔍 Checking Python dependencies...")
    missing_packages = []
    
    for package_import, package_install in required_packages.items():
        try:
            __import__(package_import)
            print(f"✅ {package_install} is installed")
        except ImportError:
            print(f"❌ {package_install} is missing")
            missing_packages.append(package_install)
    
    if missing_packages:
        print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            print("✅ All Python packages installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error installing packages: {e}")
            print("💡 Try running: pip install aiohttp aiohttp-cors")
            sys.exit(1)
    else:
        print("✅ All Python dependencies are installed!\n")

def check_ffmpeg():
    print("🔍 Checking FFmpeg installation...")
    
    if shutil.which("ffmpeg"):
        print("✅ FFmpeg is installed")
        try:
            result = subprocess.run(["ffmpeg", "-version"], 
                                  capture_output=True, text=True, timeout=5)
            version_line = result.stdout.split('\n')[0]
            print(f"   {version_line}")
        except:
            pass
        return True
    
    print("⚠️  FFmpeg not found - required for streaming")
    print("💡 Install FFmpeg:")
    print("   - Windows: winget install Gyan.FFmpeg")
    print("   - Linux: sudo apt install ffmpeg")
    print("   - macOS: brew install ffmpeg")
    return False

def setup_directories():
    print("📁 Setting up directories...")
    Path('hls').mkdir(exist_ok=True)
    print("✅ hls/ directory ready\n")

def main_setup():
    print("=" * 60)
    print("🎮 ASTERISK - Minimal HLS Server Setup")
    print("=" * 60)
    print()
    
    check_and_install_python_packages()
    check_ffmpeg()
    setup_directories()
    
    print("=" * 60)
    print("✅ Setup complete! Starting HLS file server...")
    print("=" * 60)
    print()

if __name__ == "__main__":
    main_setup()

from aiohttp import web
import aiohttp_cors

HLS_DIR = Path("hls")

async def serve_hls(request):
    filename = request.match_info['filename']
    filepath = HLS_DIR / filename
    
    if not filepath.exists():
        return web.Response(status=404, text="File not found")
    
    if filename.endswith('.m3u8'):
        content_type = 'application/vnd.apple.mpegurl'
    elif filename.endswith('.ts'):
        content_type = 'video/MP2T'
    else:
        content_type = 'application/octet-stream'
    
    with open(filepath, 'rb') as f:
        content = f.read()
    
    return web.Response(body=content, content_type=content_type)

def create_app():
    app = web.Application()
    
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    
    app.router.add_get('/hls/{filename}', serve_hls)
    
    for route in list(app.router.routes()):
        cors.add(route)
    
    print("✅ Minimal HLS server configured")
    print("   Routes:")
    print("   GET  /hls/{filename}  - Serves .m3u8 and .ts files")
    
    return app

if __name__ == "__main__":
    try:
        print("\n🚀 Starting ASTERISK HLS File Server...")
        print(f"📍 HLS Endpoint: http://localhost:5001/hls/stream.m3u8")
        print(f"📁 Serving from: {Path('hls').absolute()}")
        print("\n💡 All streaming logic is handled by the main app_aiohttp.py server")
        print("💡 This server only serves HLS files (.m3u8 and .ts)")
        print("\n💡 Press Ctrl+C to stop the server\n")
        
        app = create_app()
        web.run_app(app, host="0.0.0.0", port=5001)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)