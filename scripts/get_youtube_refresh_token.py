"""
Run this ONCE on your own machine (not in GitHub Actions) to get a refresh
token for your YouTube channel. It opens a browser for you to log in and
grant upload access, then prints the refresh token to paste into your
GitHub repo secrets as YOUTUBE_REFRESH_TOKEN.

Requires client_secret.json downloaded from Google Cloud Console
(OAuth client, type "Desktop app") in the same folder you run this from.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    print("\n--- Save these as GitHub repo secrets ---")
    print(f"YOUTUBE_CLIENT_ID={creds.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={creds.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
