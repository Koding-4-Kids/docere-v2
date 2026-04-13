# Testing Error Boundary & Toast Notifications

How to verify the Error Boundary and Toast system (no test scaffolding in the app—use real flows or the steps below).

---

## Prerequisites

- App running: backend on port 8000, frontend on port 5173 (see [Developer Setup](DEVELOPER_SETUP.md)).
- For toasts from real actions: backend + env set up so you can use courses, conversations, and meetings.

---

## 1. Error Boundary (recovery UI instead of white screen)

**Goal:** When a component throws during render, the app shows “Something went wrong” and a Reload button instead of a blank screen.

1. In `frontend/src/pages/ChatPage.tsx`, find the main `return (` (the one that returns the layout with Sidebar and main content).
2. Add this line **inside** the root `<div>`, right after the opening tag:
   ```tsx
   {(() => { throw new Error('Test error boundary') })()}
   ```
3. Save and reload http://localhost:5173. You should see the recovery screen: title “Something went wrong”, message “An unexpected error occurred. Please reload the page.”, and a **Reload** button.
4. Click **Reload** to confirm the button works.
5. **Remove the line** you added, save, and reload so the app works normally again.

---

## 2. Toasts (top-right, stack, auto-dismiss)

**Success toast (green)** — Meeting booked:

- With backend and courses set up: start or open a conversation, use a message/flow that offers “Book a meeting”, open the meeting scheduler, pick a slot, and confirm. A **green** toast “Meeting booked successfully” should appear in the **top-right**, auto-dismiss after a few seconds, and be dismissible with the × button.

**Info toast (blue)** — Conversation deleted:

- In the sidebar, delete a conversation. A **blue** toast “Conversation deleted” should appear in the top-right.

**Error toast (red)** — API failure:

- **Option A:** Stop the backend, then try to sign in at http://localhost:5173. A **red** toast should appear (e.g. “Can’t reach the server…” or “Something went wrong. Please try again. (API Error 500)”).
- **Option B:** With the app open, stop the backend, then send a message or delete a conversation. A **red** toast with the error message should appear.

**Behavior to confirm:**

- Toasts appear in the **top-right** and **stack** vertically.
- Each toast **auto-dismisses** after about 4 seconds.
- The **×** button on each toast dismisses it immediately.

---

## 3. Quick checklist

| Test | Action | Expected |
|------|--------|----------|
| Error Boundary | Add throw in ChatPage render → reload | “Something went wrong” + Reload button |
| Reload | Click Reload | Page reloads |
| Success toast | Book a meeting (full setup) | Green toast top-right |
| Info toast | Delete a conversation | Blue toast top-right |
| Error toast | Login with backend stopped, or trigger API call with backend down | Red toast top-right |
| Stacking | Trigger multiple toasts quickly | Multiple toasts stack |
| Dismiss | Click × on a toast | Toast disappears |

---

## Files involved

- **Error Boundary:** `frontend/src/components/ErrorBoundary.tsx`
- **Toasts:** `frontend/src/components/Toast.tsx`, `frontend/src/hooks/useToast.tsx`
- **Wiring:** `frontend/src/App.tsx` (ErrorBoundary + ToastProvider); toasts used in `App.tsx` (login) and `frontend/src/pages/ChatPage.tsx` (meeting booked, conversation deleted, send-message errors).
