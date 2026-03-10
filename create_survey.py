"""
Create "How Do You Actually Study?" Google Form via the Forms API.
Run:  python3 create_survey.py
It will open your browser for Google sign-in, then print the form URL.
"""

import json, os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]

SCOPES = ["https://www.googleapis.com/auth/forms.body"]

CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


def authenticate():
    flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
    creds = flow.run_local_server(port=0)
    return creds


def create_form(creds):
    service = build("forms", "v1", credentials=creds, static_discovery=False)

    # Step 1 — create a blank form
    form = service.forms().create(body={
        "info": {"title": "How Do You Actually Study?"}
    }).execute()
    form_id = form["formId"]

    # Step 2 — batch update with all questions
    requests = []
    idx = 0  # insertion index (increments per question)

    def add_choice_question(title, choices, required=True):
        nonlocal idx
        requests.append({
            "createItem": {
                "item": {
                    "title": title,
                    "questionItem": {
                        "question": {
                            "required": required,
                            "choiceQuestion": {
                                "type": "RADIO",
                                "options": [{"value": c} for c in choices],
                            }
                        }
                    }
                },
                "location": {"index": idx}
            }
        })
        idx += 1

    def add_checkbox_question(title, choices, required=True):
        nonlocal idx
        requests.append({
            "createItem": {
                "item": {
                    "title": title,
                    "questionItem": {
                        "question": {
                            "required": required,
                            "choiceQuestion": {
                                "type": "CHECKBOX",
                                "options": [{"value": c} for c in choices],
                            }
                        }
                    }
                },
                "location": {"index": idx}
            }
        })
        idx += 1

    def add_text_question(title, paragraph=False, required=True):
        nonlocal idx
        requests.append({
            "createItem": {
                "item": {
                    "title": title,
                    "questionItem": {
                        "question": {
                            "required": required,
                            "textQuestion": {
                                "paragraph": paragraph,
                            }
                        }
                    }
                },
                "location": {"index": idx}
            }
        })
        idx += 1

    # --- Questions ---

    # Q1: Contact info for giveaway
    add_text_question(
        "Email or phone number (for the $50 Amazon gift card giveaway)",
        paragraph=False,
        required=True,
    )

    # Q2: Year
    add_choice_question("What year are you?", [
        "Freshman",
        "Sophomore",
        "Junior",
        "Senior",
        "Grad student",
    ])

    # Q3: Major
    add_choice_question("What's your major area?", [
        "STEM (CS, Engineering, Math, Science)",
        "Business / Econ",
        "Humanities / Social Science",
        "Arts / Design",
        "Health / Pre-med",
        "Other",
    ])

    # Q4: Study methods
    add_checkbox_question("How do you usually study for exams? (Select all that apply)", [
        "Re-read notes / textbook",
        "Practice problems / past exams",
        "Flashcards (physical or digital)",
        "Watch YouTube / video explanations",
        "Study groups",
        "AI tools (ChatGPT, Claude, etc.)",
        "Tutoring (in-person or online)",
        "I mostly wing it",
    ])

    # Q5: Tools
    add_checkbox_question("What tools do you currently use for studying? (Select all that apply)", [
        "ChatGPT / Claude / AI chatbots",
        "Quizlet",
        "Anki",
        "Notion",
        "Google Docs / Slides",
        "Khan Academy",
        "Chegg / Course Hero",
        "None really — just my notes",
    ])

    # Q6: AI usage
    add_checkbox_question("If you use AI for studying, what do you use it for? (Select all that apply)", [
        "Explaining concepts I don't understand",
        "Summarizing readings / notes",
        "Generating practice questions",
        "Checking my work / homework help",
        "Writing assistance",
        "I don't use AI for studying",
    ])

    # Q7: Biggest frustration
    add_text_question(
        "What's your biggest frustration when studying? (1-2 sentences)",
        paragraph=True,
        required=False,
    )

    # Q8: Dream AI tutor feature
    add_text_question(
        "If an AI tutor could do ONE thing perfectly for you, what would it be? (1-2 sentences)",
        paragraph=True,
        required=False,
    )

    # Q9: Would you use it
    add_choice_question("Would you use an AI tutor connected to your actual course materials and grades?", [
        "Yeah, that sounds super useful",
        "Maybe — depends on how it works",
        "Probably not",
        "No, I prefer studying on my own",
    ])

    # Update the form description too
    requests.append({
        "updateFormInfo": {
            "info": {
                "description": (
                    "Quick 2-min survey about how you study and the tools you use. "
                    "Your answers help us build better tools for students. "
                    "All responses are anonymous.\n\n"
                    "Complete the survey for a chance to win a $50 Amazon gift card!"
                ),
            },
            "updateMask": "description",
        }
    })

    service.forms().batchUpdate(
        formId=form_id,
        body={"requests": requests},
    ).execute()

    form_url = form["responderUri"]
    print(f"\nForm created!\n")
    print(f"  Edit:    https://docs.google.com/forms/d/{form_id}/edit")
    print(f"  Share:   {form_url}")
    print()
    return form_url


if __name__ == "__main__":
    creds = authenticate()
    create_form(creds)
