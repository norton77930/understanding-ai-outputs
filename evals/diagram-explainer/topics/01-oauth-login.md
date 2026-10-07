- Language: en
- Expected diagram type: `sequenceDiagram`

## Source

When you click "Log in with" on a website, the site (the app) never sees your password. It uses the OAuth authorization-code flow instead. First, the app sends your browser to the authorization server, together with its client ID, the permissions it wants and a random state value. You sign in there and approve the request. The server then redirects your browser back to the app with a short-lived authorization code. The browser only carries this code, and the code alone gives no access. Next, the app's back end sends the code to the server's token endpoint, with its client secret or a PKCE verifier, and receives an access token. Finally, the app calls the API with that token, and the API returns your data. The app also checks that the state value in the redirect matches the one it sent.

## Reader should understand

- The app sends the browser to the authorization server, and the user signs in and approves there, not in the app.
- The server sends the browser back to the app with a short-lived code, not with the token.
- The app's back end trades the code for an access token in a direct call to the server.
- The app uses the access token to call the API.

## Diagram hints

- Expected type: `sequenceDiagram` (the question is "what happens, in order, between these parties").
- Participants (4): Browser, App, Auth server, API. The user can be shown as a note on the sign-in message, not as a fifth participant.
- Key messages (about 9): click login; redirect to Auth server; sign in and approve; redirect back with code; send code to App; App sends code to Auth server; access token returns; App calls API with token; data returns.
- The caption should point at the difference between the two trips: the code goes through the browser, the token goes only between App and Auth server.
