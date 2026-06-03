import scripts.run_weekly_update as weekly


class FakeSession:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeJob:
    crawl_job_id = 7


class FakeService:
    calls = []

    def create_incremental(self, db, **kwargs):
        self.calls.append(("create_incremental", kwargs))
        return FakeJob()

    def run_job_by_id(self, crawl_job_id):
        self.calls.append(("run_job_by_id", crawl_job_id))

    def get_job_detail(self, db, crawl_job_id):
        self.calls.append(("get_job_detail", crawl_job_id))
        return {
            "crawl_job_id": crawl_job_id,
            "status": "completed",
            "date_from": "2026-05-14",
            "date_to": "2026-05-27",
            "total_api_calls": 0,
            "total_articles_saved": 0,
            "total_articles_duplicated": 0,
            "error_message": None,
        }


def test_run_weekly_update_uses_crawl_job_service(monkeypatch, capsys):
    fake_service = FakeService()
    fake_service.calls.clear()
    monkeypatch.setenv("WEEKLY_UPDATE_DAYS_BACK", "14")
    monkeypatch.setattr(weekly, "init_db", lambda engine: None)
    monkeypatch.setattr(weekly, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(weekly, "CrawlJobService", lambda: fake_service)

    weekly.main()

    output = capsys.readouterr().out
    assert ("create_incremental", {"days_back": 14, "include_llm_extraction": False, "include_reinsurers": False, "include_foreign_branches": False, "requested_by": "weekly_script"}) in fake_service.calls
    assert ("run_job_by_id", 7) in fake_service.calls
    assert "completed" in output
