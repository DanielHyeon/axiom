"""Evidence Redactor 단위 테스트 — Sprint 8.

비밀번호, 토큰, 이메일, 주민번호, AWS 키, 커넥션 스트링 마스킹 검증.
"""

import pytest
from app.services.evidence_redactor import EvidenceRedactor
from app.models.evidence import AnalysisEvidence, EvidenceType


@pytest.fixture
def redactor():
    return EvidenceRedactor()


class TestPasswordRedaction:
    def test_password_assignment(self, redactor):
        s = 'password = "mysecret123"'
        assert "mysecret123" not in redactor.redact(s)
        assert "REDACTED" in redactor.redact(s)

    def test_token_colon(self, redactor):
        s = "api_key: sk-1234567890abcdef"
        assert "sk-1234567890abcdef" not in redactor.redact(s)

    def test_secret_key(self, redactor):
        s = "secret_key=very_secret_value_123"
        assert "very_secret_value_123" not in redactor.redact(s)


class TestConnectionStringRedaction:
    def test_postgresql_uri(self, redactor):
        s = "postgresql://user:pass@localhost:5432/mydb"
        assert "user:pass" not in redactor.redact(s)
        assert "CONNECTION_STRING_REDACTED" in redactor.redact(s)

    def test_mongodb_uri(self, redactor):
        s = "mongodb+srv://admin:p4ssw0rd@cluster.example.com/test"
        assert "p4ssw0rd" not in redactor.redact(s)

    def test_redis_uri(self, redactor):
        s = "redis://default:secret@redis-host:6379/0"
        assert "secret" not in redactor.redact(s)


class TestTokenRedaction:
    def test_bearer_token(self, redactor):
        s = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc"
        assert "eyJhbGci" not in redactor.redact(s)
        assert "REDACTED" in redactor.redact(s)

    def test_github_token(self, redactor):
        s = "GITHUB_TOKEN=ghp_1234567890abcdef1234567890abcdef12"
        assert "ghp_" not in redactor.redact(s)

    def test_aws_key(self, redactor):
        s = "aws_key = AKIAIOSFODNN7EXAMPLE"
        assert "AKIAIOSFODNN7EXAMPLE" not in redactor.redact(s)


class TestPIIRedaction:
    def test_email(self, redactor):
        s = "user@example.com"
        result = redactor.redact(s)
        assert "user@example.com" not in result
        assert "***@***.***" in result

    def test_korean_rrn(self, redactor):
        """주민등록번호 패턴 마스킹"""
        s = "주민번호: 900101-1234567"
        result = redactor.redact(s)
        assert "1234567" not in result

    def test_no_false_positive_on_numbers(self, redactor):
        """일반 숫자는 마스킹하지 않음"""
        s = "count = 1234567890123"
        result = redactor.redact(s)
        # 13자리 숫자가 주민번호 정밀 패턴에 매칭되지 않아야 함
        # (성별 코드 1-4 체크)
        assert "1234567890123" in result


class TestJDBCRedaction:
    def test_jdbc_password(self, redactor):
        s = "jdbc:postgresql://host:5432/db?user=admin&password=secret123"
        assert "secret123" not in redactor.redact(s)

    def test_private_key(self, redactor):
        s = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        result = redactor.redact(s)
        assert "MIIEowIBAAKCAQEA" not in result
        assert "REDACTED PRIVATE KEY" in result


class TestSnippetTruncation:
    def test_long_snippet_truncated(self, redactor):
        s = "x" * 1000
        result = redactor.redact(s)
        assert len(result) <= 520  # 500 + "[truncated]"

    def test_truncation_before_regex(self, redactor):
        """긴 입력이 정규식 전에 잘리는지 확인 (ReDoS 방지)"""
        s = "a" * 600 + "password=secret"
        result = redactor.redact(s)
        assert len(result) <= 520


class TestEvidenceRedaction:
    def test_redact_evidence_object(self, redactor):
        evidence = AnalysisEvidence(
            source_file="test.java",
            code_snippet='String pwd = "admin123";',
            reasoning="password=admin123을 발견",
            confidence=0.9,
            evidence_type=EvidenceType.ANNOTATION,
        )
        safe = redactor.redact_evidence(evidence)
        assert "admin123" not in safe.code_snippet
        assert "admin123" not in safe.reasoning
        # 원본은 변경되지 않음
        assert "admin123" in evidence.code_snippet
