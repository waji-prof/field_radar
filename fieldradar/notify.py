"""Windows pop-up notification using built-in PowerShell (nothing to install)."""
import os
import subprocess
from xml.sax.saxutils import escape

_PS = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($env:FIELDRADAR_TOAST)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
"""


def notify(title, line1, line2, open_path):
    if os.name != "nt":
        return False
    uri = "file:///" + os.path.abspath(open_path).replace("\\", "/")
    a = escape(uri, {'"': "&quot;"})
    xml = (
        f'<toast activationType="protocol" launch="{a}">'
        f'<visual><binding template="ToastGeneric">'
        f"<text>{escape(title)}</text><text>{escape(line1)}</text><text>{escape(line2)}</text>"
        f"</binding></visual>"
        f'<actions><action content="Open dashboard" activationType="protocol" arguments="{a}"/></actions>'
        f"</toast>"
    )
    env = dict(os.environ, FIELDRADAR_TOAST=xml)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-WindowStyle", "Hidden", "-Command", _PS],
            env=env, timeout=30, capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False
