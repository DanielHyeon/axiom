"""axiom-shared 패키지 설치 설정.

각 서비스에서 editable 모드로 설치하여 사용한다:
    pip install -e ../shared

이렇게 하면 shared 코드를 수정해도 서비스 재설치 없이 바로 반영된다.
"""

from setuptools import find_packages, setup

setup(
    name="axiom-shared",
    version="0.1.0",
    description="Axiom 플랫폼 전 서비스 공통 라이브러리",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.100.0",
        "pydantic>=2.0.0",
        "structlog>=24.0.0",
        "python-multipart>=0.0.9",
    ],
)
