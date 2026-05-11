"""Run with: python -m webapp"""
import uvicorn


def main() -> None:
    uvicorn.run(
        "webapp.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
