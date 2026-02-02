#!/usr/bin/env python3
"""
Git 자동 커밋/푸시 스크립트
"""
import subprocess
import sys
from datetime import datetime


def run_command(cmd: list[str]) -> tuple[bool, str]:
    """명령어 실행"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def auto_commit(message: str = None, push: bool = True):
    """자동 커밋 및 푸시"""

    # 기본 메시지
    if not message:
        message = f"chore: auto-commit {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    print(f"🔄 Git 자동 커밋 시작...")
    print(f"   메시지: {message}")

    # Git add
    print("\n📝 변경사항 스테이징...")
    success, output = run_command(["git", "add", "."])
    if not success:
        print(f"❌ git add 실패: {output}")
        return False

    # 변경사항 확인
    success, status = run_command(["git", "status", "--short"])
    if not status.strip():
        print("ℹ️  변경사항 없음")
        return True

    print(f"   변경된 파일:\n{status}")

    # Git commit
    print("\n💾 커밋 생성...")
    success, output = run_command(["git", "commit", "-m", message])
    if not success:
        if "nothing to commit" in output:
            print("ℹ️  커밋할 내용 없음")
            return True
        print(f"❌ git commit 실패: {output}")
        return False

    print(f"   {output}")

    # Git push
    if push:
        print("\n🚀 원격 저장소에 푸시...")

        # 현재 브랜치 확인
        success, branch = run_command(["git", "branch", "--show-current"])
        if not success:
            print(f"❌ 브랜치 확인 실패")
            return False

        branch = branch.strip()
        print(f"   브랜치: {branch}")

        # Push
        success, output = run_command(["git", "push", "origin", branch])
        if not success:
            print(f"❌ git push 실패: {output}")
            return False

        print("   ✅ 푸시 완료!")

    print("\n✅ Git 자동 커밋 완료!")
    return True


if __name__ == "__main__":
    # 커맨드라인 인자로 메시지 받기
    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    success = auto_commit(message)
    sys.exit(0 if success else 1)
