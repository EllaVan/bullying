"""在项目根目录执行python run.py --help查看命令。"""
from psych_agent.cli import main
from pathlib import Path
import os
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)
root_dir = Path(__file__).resolve().parent

if __name__ == '__main__':
    raise SystemExit(main())
    # argv = ["extract", "--case-file", "/media/sda/wf/Bullying/ChatAgent/psych_agent_round1/data/single_case.json", "--llm-config", "/media/sda/wf/Bullying/ChatAgent/psych_agent_round1/config/llm.local.json"]
    # main(argv=argv)
