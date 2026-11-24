# Meta setup

This takes about 20 minutes and is done once. You end up with three values: a Facebook Page ID, an Instagram user ID and a Page access token that doesn't expire.

Meta renames screens from time to time. If a screen doesn't match, look for the permission names below, because those don't change.

## 1. Make Instagram a professional account and link it to the Page

1. In the Instagram app, open **Settings → Account type and tools → Switch to professional account**, and choose **Business** or **Creator**.
2. Link it to the Facebook Page. In Meta Business Suite, open **Settings → Instagram accounts → Connect**. On the Page itself, it's **Settings → Linked accounts → Instagram**.

## 2. Create a Meta app

1. Sign in at [developers.facebook.com](https://developers.facebook.com/) with the Facebook account that manages the Page, and open **My Apps → Create App**.
2. Choose the **Business** type (it may be listed under the "Other" use case). Name it something like "Shaadi Planner Pro Autopilot".
3. In the app's settings, add a **Privacy Policy URL** (your site's privacy page) and set the **App Mode** to **Live**. Posts made by an app in Development mode can be hidden from the public.

As the app's admin, posting to your own Page and Instagram account doesn't need Meta's App Review.

## 3. Get a token in Graph API Explorer

1. Open [Graph API Explorer](https://developers.facebook.com/tools/explorer/) and select your app.
2. Under **User or Page**, choose **Get User Access Token** and add these permissions:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `instagram_basic`
   - `instagram_content_publish`
   - `business_management`
3. Click **Generate Access Token** and approve the Page and the Instagram account in the dialog.

## 4. Exchange it for a token that doesn't expire

The Explorer token lasts about an hour. From the repository folder, run:

```bash
python -m autopilot setup-token
```

Paste the app ID and app secret (**App settings → Basic**) and the Explorer token. Nothing you paste is echoed or saved. The command prints the Page ID, the linked Instagram user ID and a Page token.

Check the token in the [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/). It should say **Expires: Never**.

## 5. Store the secrets

In the GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
| --- | --- |
| `SPP_FB_PAGE_ID` | Page ID |
| `SPP_IG_USER_ID` | Instagram user ID |
| `SPP_FB_PAGE_TOKEN` | Page token |

Never commit the token or paste it into a post, issue or chat.

To test locally, export the same three variables and run `python -m autopilot check --brand shaadi-planner-pro`.

## When the token stops working

Changing your Facebook password, removing the app from your account, or losing admin access to the Page revokes the token. The daily run then fails with an authentication error. Repeat steps 3 to 5 to fix it.
