"""
Windows desktop notification helper.
Uses plyer if installed, falls back silently.
"""


def notify(title: str, message: str, timeout: int = 8) -> None:
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="OSINTNEWS",
            timeout=timeout,
        )
    except Exception:
        pass  # Notifications optional — never crash the app
