# Meta setup

This takes about 20 minutes and is done once. You end up with three values: a Facebook Page ID, an Instagram user ID and a Page access token that doesn't expire.

Meta renames screens from time to time. If a screen doesn't match, look for the permission names below, because those don't change.

## 1. Make Instagram a professional account and link it to the Page

1. In the Instagram app, open **Settings → Account type and tools → Switch to professional account**, and choose **Business** or **Creator**.
2. Link it to the Facebook Page. In Meta Business Suite, open **Settings → Instagram accounts → Connect**. On the Page itself, it's **Settings → Linked accounts → Instagram**.

## 2. Create a Meta app

1. Sign in at [developers.facebook.com](https://developers.facebook.com/) with the Facebook account that manages the Page, and open **My Apps → Create App**. Name it something like "Shaadi Planner Pro Autopilot".
2. On **Add use cases**, filter by **Content management** and tick:
   - **Manage everything on your Page**
   - **Manage messaging & content on Instagram**

   Leave the ads, Marketing API and Threads options unticked.
3. If it asks for a business portfolio, pick the one that owns your Page, or skip it. Either works for your own Page.
4. In the app dashboard, open **Use cases**:
   - Next to **Manage everything on your Page**, click **Customize** and **Add** `pages_manage_posts` and `pages_read_engagement`.
   - Next to **Manage messaging & content on Instagram**, click **Customize**, choose **API setup with Facebook login** (not Instagram login), and **Add** `instagram_basic` and `instagram_content_publish`.
5. In **App settings → Basic**, add a **Privacy Policy URL** (your site's privacy page). Then set the app to **Live**. Posts made by an app in Development mode can be hidden from the public.

As the app's admin, posting to your own Page and Instagram account doesn't need Meta's App Review.

## 3. Get a token in Graph API Explorer

1. Open [Graph API Explorer](https://developers.facebook.com/tools/explorer/) and select your app under **Meta App**.
2. In the **Permissions** dropdown, tick all six:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `instagram_basic`
   - `instagram_content_publish`
   - `business_management`

   If some are missing from the dropdown, they haven't been added to the app's use cases yet. Finish step 2.4, then refresh the Explorer.
3. Click **Generate Access Token** and approve the Page and the Instagram account in the pop-up.

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
