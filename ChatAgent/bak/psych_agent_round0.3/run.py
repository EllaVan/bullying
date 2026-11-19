"""在项目根目录执行python run.py --help查看命令。"""
import os
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)

from psych_agent.cli import main

if __name__ == '__main__':
    # raise SystemExit(main())
    argv = [
        'dialogue-replay',
        '--plan', 's01',
        '--output', 'outputs/demo_s01'
    ]
    main(argv)
