from app.utils.hashing import article_dedup_hash


def test_url_hash_dedup_stable():
    assert article_dedup_hash("https://example.com/a", "A", "B") == article_dedup_hash("https://example.com/a", "X", "Y")


def test_content_hash_fallback():
    assert article_dedup_hash(None, "A", "B") == article_dedup_hash("", "A", "B")
