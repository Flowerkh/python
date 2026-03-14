import streamlit.web.cli as stcli
import os, sys
def resolve_path(path):
    resolved_path = os.path.abspath(os.path.join(os.getcwd(), path))
    return resolved_path

if __name__ == "__main__":
    # 실행할 파일명을 정확히 적어주세요
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("blog_app.py"),
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())