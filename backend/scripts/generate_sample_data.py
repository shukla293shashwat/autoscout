"""Deterministic sample data generator for AutoScout (Phase 1).

Generates a realistic one-week dataset for persona "Maya Rao, sales operations
manager at a 30-person B2B SaaS company", embedding three hidden repetitive
patterns plus deliberate non-patterns and noise. Output is deterministic
(fixed seed) and committed under data/sample/.

Usage:
    cd backend
    python scripts/generate_sample_data.py
"""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20250106
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"

# The work week: Mon 2025-01-06 .. Fri 2025-01-10
WEEK_START = datetime(2025, 1, 6)
WEEK_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

rng = random.Random(SEED)

# ---------------------------------------------------------------------------
# Vocabulary pools for noise and non-pattern content
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Priya", "Alex", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Taylor",
    "Devon", "Avery", "Harper", "Quinn", "Rowan", "Skyler", "Drew", "Jamie",
    "Kai", "Reese", "Emerson", "Finley", "Harley", "Marlowe", "Noel", "Sage",
    "Tatum", "Blake", "Charlie", "Dakota", "Elliot", "Frankie",
]
LAST_NAMES = [
    "Mehta", "Nguyen", "Patel", "Garcia", "Kim", "Okafor", "Silva", "Haddad",
    "Novak", "Fischer", "Rossi", "Dubois", "Andersson", "Costa", "Hoffman",
    "Iyer", "Kaur", "Sharma", "Chen", "Moreau", "Bauer", "Kowalski", "Sato",
    "Ali", "Reyes", "Mendes", "Ferrari", "Weber", "Larsen", "Petrov",
]
COMPANIES = [
    "Northwind Logistics", "Apex Retail Group", "Brightline Media",
    "Corevault Systems", "Delta Harbor Foods", "Evergreen Utilities",
    "Farsight Analytics", "Greenfield Pharma", "Helio Mobility",
    "Ironclad Insurance", "Juniper Networks", "Krypton Labs", "Lakeside Hotels",
    "Meridian Bank", "Nimbus Cloud", "Orbital Freight", "Pinnacle Legal",
    "Quantum Payments", "Ridgeline Mining", "Solaris Energy", "Timberline Auto",
    "Umbrella Catering", "Vertex Robotics", "Westbrook Hotels", "Zenith Health",
    "Altura Airlines", "Bluepeak Media", "Cedar Point Retail", "Dockside Marine",
    "Ember Logistics",
]
INDUSTRIES = ["logistics", "retail", "media", "SaaS", "healthcare", "fintech", "manufacturing"]
NEWSLETTERS = [
    ("Sales Hacker Weekly", "Top 10 outbound cadences for 2025"),
    ("Revenue Digest", "Why your demo-to-close rate is slipping"),
    ("SaaStr Daily", "The state of PLG in 2025"),
    ("GTM Wire", "Territory planning myths busted"),
    ("Pipeline Insider", "Cold email deliverability fixes"),
    ("CRM Gazette", "Clean up your CRM in 30 minutes"),
    ("Ops Overlord", "Automation ideas from revenue ops teams"),
    ("Lead Flow Weekly", "Inbound scoring models that work"),
    ("Deal Room", "Negotiation tactics for multi-threaded deals"),
    ("Churn Watch", "Five early signals of account risk"),
    ("Quota Crusher", "Building a repeatable weekly rhythm"),
    ("Field Notes", "What AEs really want from ops"),
]
PROJECT_UPDATES = [
    ("Q1 territory plan", "Draft territories are ready for review; please add comments by EOD."),
    ("CRM hygiene sweep", "Duplicate accounts reduced by 18% this week. Keep flagging stragglers."),
    ("New SDR pod", "Two new SDRs start Monday; ramp schedule is attached."),
    ("Pricing experiment", "Variant B shows +6% demo bookings. Recommend shipping it."),
    ("Webinar follow-up", "142 registrants, 61 live. Reminder sequences queued."),
    ("Onboarding revamp", "Time-to-first-value dropped from 21 to 14 days."),
    ("Partner referral program", "Three partners signed; MDF paperwork pending."),
    ("Forecast hygiene", "Commit category cleaned up; two deals moved to upside."),
]
ALL_NAMES = [f"{f} {l}" for f in FIRST_NAMES for l in LAST_NAMES]


def email_addr(name: str, domain: str | None = None) -> str:
    handle = name.lower().replace(" ", ".")
    return f"{handle}@{domain}" if domain else f"{handle}@example.com"


def pick(seq: list) -> object:
    return rng.choice(seq)


# ---------------------------------------------------------------------------
# Pattern B: Inbound demo requests (emails + reply templates)
# ---------------------------------------------------------------------------
DEMO_COMPANIES = [
    ("Northwind Logistics", "Priya Mehta", "priya.mehta@northwindlogistics.com", "ops"),
    ("Apex Retail Group", "Jordan Reyes", "jordan.reyes@apexretail.com", "revops"),
    ("Brightline Media", "Sam Okafor", "sam.okafor@brightlinemedia.com", "demand"),
    ("Corevault Systems", "Riley Chen", "riley.chen@corevault.io", "sales"),
    ("Delta Harbor Foods", "Casey Silva", "casey.silva@deltaharbor.com", "operations"),
    ("Evergreen Utilities", "Morgan Novak", "morgan.novak@evergreenutil.com", "procurement"),
    ("Farsight Analytics", "Avery Fischer", "avery.fischer@farsight.ai", "growth"),
    ("Greenfield Pharma", "Harper Costa", "harper.costa@greenfieldpharma.com", "commercial"),
    ("Helio Mobility", "Quinn Haddad", "quinn.haddad@heliomobility.com", "sales"),
    ("Ironclad Insurance", "Devon Rossi", "devon.rossi@ironcladins.com", "ops"),
    ("Juniper Networks", "Taylor Iyer", "taylor.iyer@junipernets.com", "gtm"),
    ("Krypton Labs", "Kai Sharma", "kai.sharma@kryptonlabs.io", "revops"),
]
DEMO_VARIANTS = [
    "We're evaluating CRM automation tools and your product came up. Could we book a demo?",
    "I'd like a demo of the platform for our sales team (~12 reps). What times work this week?",
    "Interested in seeing how this works with our inbound flow. Please send a demo link.",
    "Our team lead asked me to reach out — could someone show us a quick demo?",
    "Hi, we're trialling a few tools for pipeline hygiene. Can we schedule a demo?",
    "Looking for a demo to share with our VP Sales next week. Any availability?",
    "We saw your webinar and would love a walkthrough of the product.",
    "Could you set up a demo? We're a 40-person team drowning in manual spreadsheet work.",
    "Requesting a demo of your solution — we need to automate lead routing ASAP.",
    "My name is with the revenue team; I'd like a demo focused on reporting.",
    "Can we get a demo for our ops group? Especially interested in integrations.",
    "Would appreciate a demo link — evaluating three vendors this quarter.",
]
REPLY_TEMPLATES = [
    "Hi {first},\n\nThanks for your interest in AutoScout! I'd love to show you around.\n\n"
    "Here's my calendar link: https://cal.com/maya/30min\n\n"
    "Feel free to grab any slot that works for you. Looking forward to connecting!\n\n"
    "Best,\nMaya",
    "Hi {first},\n\nGreat to hear from you! Happy to set up a demo.\n\n"
    "You can pick a time here: https://cal.com/maya/30min\n\n"
    "If you have specific workflows you'd like to see, just reply and I'll prep them.\n\n"
    "Cheers,\nMaya",
    "Hi {first},\n\nThanks for reaching out — I'd be glad to walk you through the product.\n\n"
    "Grab a slot that suits you: https://cal.com/maya/30min\n\n"
    "Talk soon!\n\nMaya",
]

# ---------------------------------------------------------------------------
# Pattern A: Weekly pipeline status email templates
# ---------------------------------------------------------------------------
STATUS_SUBJECTS = [
    "Weekly Pipeline Status - {date}",
    "Weekly Pipeline Status – {date}",
    "Pipeline Status Update - week of {date}",
    "Weekly Status: Pipeline & Deals - {date}",
]
STATUS_BODY_TEMPLATE = """Hi all,

Here's the weekly pipeline status as of {date}.

Pipeline summary
- Total open pipeline: {total}
- New leads added this week: {new_leads}
- Deals advancing to next stage: {advancing}
- Deals at risk / stalled: {at_risk}
- Forecast for the quarter: {forecast}

Key updates
- {update1}
- {update2}
- {update3}

Action items
- Review the two deals flagged at risk before Monday's standup.
- Confirm demo slots for the new inbound leads.

Full details are in the leads sheet. Shout if anything looks off.

Thanks,
Maya
Sales Operations"""

STATUS_SUBJECTS_ALT = [
    "Weekly pipeline status – {date}",
    "Pipeline update for the week of {date}",
    "Friday status: pipeline, leads & deals – {date}",
    "Weekly Pipeline Snapshot - {date}",
]
STATUS_BODY_TEMPLATE_ALT = """Hi team,

Quick summary of where the pipeline stands ({date}):

* Open pipeline: {total} ({new_leads} new leads this week)
* Advancing: {advancing} deals moved stage; {at_risk} need attention
* Forecast: {forecast}

Notes:
- {update1}
- {update2}

The updated leads sheet is attached as usual. Let me know if you spot anything
missing before the forecast call.

Best,
Maya"""

# ---------------------------------------------------------------------------
# Pattern C: Meeting follow-up email templates
# ---------------------------------------------------------------------------
FOLLOWUP_SUBJECTS = [
    "Follow-up: {meeting}",
    "Recap & action items – {meeting}",
    "Notes from {meeting}",
    "Follow up from our {meeting}",
]
FOLLOWUP_BODY_TEMPLATE = """Hi all,

Thanks for the discussion today. Quick recap and action items:

Recap
- {summary1}
- {summary2}

Action items
- {action1}
- {action2}

I'll send the updated doc by EOD. Ping me if I missed anything.

Best,
Maya"""


# ---------------------------------------------------------------------------
# Email builders
# ---------------------------------------------------------------------------
def make_email(
    eid: str,
    day: int,
    hour: int,
    minute: int,
    frm: str,
    to: str,
    subject: str,
    body: str,
    label: str = "inbox",
) -> dict[str, str]:
    """Build one emails.csv row. Dates intentionally use mixed formats."""
    dt = WEEK_START + timedelta(days=day) + timedelta(hours=hour, minutes=minute)
    style = rng.choice(["iso", "slash", "human"])
    if style == "iso":
        date = dt.strftime("%Y-%m-%d %H:%M")
    elif style == "slash":
        date = dt.strftime("%m/%d/%Y %I:%M %p")
    else:
        date = dt.strftime("%d-%b-%Y %H:%M")
    return {
        "id": eid,
        "date": date,
        "from": frm,
        "to": to,
        "subject": subject,
        "body": body,
        "labels": label,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "meeting_notes").mkdir(exist_ok=True)

    emails: list[dict[str, str]] = []
    leads: list[dict[str, str]] = []
    tasks: list[dict[str, str]] = []
    gt_patterns: list[dict] = []
    non_patterns: list[dict] = []

    maya = email_addr("Maya Rao", "brightloop.io")
    leadership = email_addr("Dana Whitfield", "brightloop.io")

    # ------------------------------------------------------------------
    # Pattern A: weekly pipeline status email (Friday) — 1 occurrence
    # ------------------------------------------------------------------
    pattern_a_email_ids: list[str] = []
    pattern_a_task_ids: list[str] = []
    eid = "E001"
    friday = 4
    body = STATUS_BODY_TEMPLATE.format(
        date="Friday, Jan 10, 2025",
        total="$1.84M",
        new_leads="30",
        advancing="7",
        at_risk="3",
        forecast="$612K",
        update1="Northwind Logistics moved to proposal stage.",
        update2="Two demos booked from last week's inbound batch.",
        update3="Renewal for Meridian Bank pushed to next month.",
    )
    emails.append(make_email(
        eid, friday, 16, 20, maya, leadership,
        "Weekly Pipeline Status - Friday, Jan 10, 2025", body, "sent",
    ))
    pattern_a_email_ids.append(eid)
    eid = "E002"
    body = STATUS_BODY_TEMPLATE_ALT.format(
        date="Monday, Jan 6, 2025",
        total="$1.79M",
        new_leads="24",
        advancing="5",
        at_risk="4",
        forecast="$598K",
        update1="Apex Retail Group asked for a security questionnaire.",
        update2="Two stalled deals re-engaged after outreach.",
    )
    emails.append(make_email(
        eid, 0, 17, 5, maya, leadership,
        "Weekly pipeline status – Monday, Jan 6, 2025", body, "sent",
    ))
    pattern_a_email_ids.append(eid)
    eid = "E003"
    body = STATUS_BODY_TEMPLATE.format(
        date="Thursday, Jan 9, 2025",
        total="$1.81M",
        new_leads="27",
        advancing="6",
        at_risk="3",
        forecast="$605K",
        update1="Brightline Media demo went well; proposal out Monday.",
        update2="Corevault Systems procurement review scheduled.",
        update3="Helio Mobility trial extended by two weeks.",
    )
    emails.append(make_email(
        eid, 3, 16, 45, maya, leadership,
        "Weekly Status: Pipeline & Deals - Thursday, Jan 9, 2025", body, "sent",
    ))
    pattern_a_email_ids.append(eid)
    eid = "E004"
    body = STATUS_BODY_TEMPLATE_ALT.format(
        date="Wednesday, Jan 8, 2025",
        total="$1.77M",
        new_leads="22",
        advancing="4",
        at_risk="5",
        forecast="$590K",
        update1="Ironclad Insurance stalled — champion went quiet.",
        update2="Greenfield Pharma asked for ROI numbers.",
    )
    emails.append(make_email(
        eid, 2, 15, 30, maya, leadership,
        "Weekly Pipeline Snapshot - Wednesday, Jan 8, 2025", body, "sent",
    ))
    pattern_a_email_ids.append(eid)
    eid = "E005"
    body = STATUS_BODY_TEMPLATE.format(
        date="Tuesday, Jan 7, 2025",
        total="$1.72M",
        new_leads="18",
        advancing="3",
        at_risk="5",
        forecast="$575K",
        update1="Juniper Networks demo rescheduled to next week.",
        update2="Orbital Freight signed a one-year extension.",
        update3="Two new SDRs ramping on the new playbook.",
    )
    emails.append(make_email(
        eid, 1, 16, 10, maya, leadership,
        "Pipeline update for the week of Tuesday, Jan 7, 2025", body, "sent",
    ))
    pattern_a_email_ids.append(eid)
    eid = "E006"
    body = STATUS_BODY_TEMPLATE_ALT.format(
        date="Friday, Jan 10, 2025 (second pass)",
        total="$1.85M",
        new_leads="31",
        advancing="7",
        at_risk="3",
        forecast="$615K",
        update1="Two proposals sent — Northwind and Brightline.",
        update2="Security review started for Apex Retail.",
    )
    emails.append(make_email(
        eid, friday, 17, 30, maya, leadership,
        "Friday status: pipeline, leads & deals – Jan 10, 2025", body, "sent",
    ))
    pattern_a_email_ids.append(eid)

    tasks.append({
        "id": "T001",
        "title": "Send weekly pipeline status to leadership",
        "due": "2025-01-10",
        "status": "done",
        "project": "Reporting",
        "notes": "Summarize deals from leads sheet, send before 5pm.",
    })
    pattern_a_task_ids.append("T001")
    tasks.append({
        "id": "T002",
        "title": "Compile weekly pipeline status email",
        "due": "01/17/2025",
        "status": "todo",
        "project": "Reporting",
        "notes": "Same as every Friday: pull numbers, write summary, send to Dana.",
    })
    pattern_a_task_ids.append("T002")

    # ------------------------------------------------------------------
    # Pattern B: inbound demo request emails (12) + Maya's replies (12)
    # ------------------------------------------------------------------
    pattern_b_ids: list[str] = []
    pattern_b_reply_ids: list[str] = []
    for i, (company, contact, addr, role) in enumerate(DEMO_COMPANIES):
        day = i % 5
        eid = f"E{10 + i * 2:03d}"
        first = contact.split()[0]
        subject_variants = [
            f"Demo request - {company}",
            f"I'd like a demo",
            f"Demo of your product for {company}",
            f"Interested in a demo",
            f"Request: product demo for {company}",
        ]
        body = (
            f"Hi,\n\n{DEMO_VARIANTS[i]}\n\n"
            f"We're a {role} team at {company} and we're comparing a few options. "
            f"Happy to work around your calendar.\n\nThanks,\n{first}\n{contact}\n{company}"
        )
        emails.append(make_email(
            eid, day, 8 + (i % 8), (i * 7) % 60, addr, maya,
            subject_variants[i % len(subject_variants)], body, "inbox",
        ))
        pattern_b_ids.append(eid)

        eid = f"E{11 + i * 2:03d}"
        reply = REPLY_TEMPLATES[i % len(REPLY_TEMPLATES)].format(first=first)
        emails.append(make_email(
            eid, day, 9 + (i % 8), (i * 7 + 3) % 60, maya, addr,
            f"Re: {subject_variants[i % len(subject_variants)]}", reply, "sent",
        ))
        pattern_b_reply_ids.append(eid)

    gt_patterns.append({
        "id": "A",
        "name": "Weekly pipeline status email",
        "description": "Every Friday (and often on other days) Maya writes a nearly identical "
                       "email to leadership summarizing deals from the leads sheet.",
        "minutes_per_occurrence": 25,
        "source_ids": pattern_a_email_ids + pattern_a_task_ids,
        "kinds": ["email", "task"],
    })
    gt_patterns.append({
        "id": "B",
        "name": "Inbound lead copy-paste",
        "description": "Maya manually copies inbound demo-request emails into leads.csv and "
                       "replies with a near-identical template.",
        "minutes_per_occurrence": 6,
        "source_ids": pattern_b_ids + pattern_b_reply_ids,
        "kinds": ["email"],
    })

    # ------------------------------------------------------------------
    # Pattern C: meeting follow-ups — 5 meetings with notes, follow-up
    # emails, and derived tasks
    # ------------------------------------------------------------------
    meeting_specs = [
        ("pipeline_standup", "Weekly Pipeline Standup", 0),
        ("sd_ramp_sync", "SDR Ramp Sync", 1),
        ("demo_review", "Demo Feedback Review", 2),
        ("forecast_call", "Forecast & Deal Desk Call", 3),
        ("ops_retro", "Revenue Ops Retro", 4),
    ]
    pattern_c_note_ids: list[str] = []
    pattern_c_email_ids: list[str] = []
    pattern_c_task_ids: list[str] = []
    actions = [
        ("Maya to send updated status deck to Dana", "Send status deck"),
        ("Sam to prep the Northwind proposal", "Prep Northwind proposal"),
        ("Jordan to clean up duplicate accounts", "Clean duplicate accounts"),
        ("Casey to update the security questionnaire", "Update security questionnaire"),
        ("Riley to book two customer calls", "Book customer calls"),
        ("Morgan to review SDR ramp metrics", "Review SDR ramp metrics"),
        ("Avery to rebuild the lead scoring model", "Rebuild lead scoring model"),
        ("Harper to share competitor battlecards", "Share battlecards"),
        ("Quinn to refresh demo environment data", "Refresh demo data"),
        ("Devon to close out Q4 forecast gaps", "Close forecast gaps"),
        ("Taylor to document the follow-up checklist", "Document checklist"),
        ("Kai to audit webhook failures", "Audit webhook failures"),
        ("Priya to draft the partner one-pager", "Draft partner one-pager"),
        ("Alex to schedule the pricing review", "Schedule pricing review"),
        ("Sam to update CRM stages", "Update CRM stages"),
    ]
    for mi, (stem, meeting, day) in enumerate(meeting_specs):
        note_path = OUT_DIR / "meeting_notes" / f"{stem}.txt"
        a1, a2 = actions[mi * 2], actions[mi * 2 + 1]
        attendees = ["Maya Rao", "Dana Whitfield", a1[0].split(" to ")[0], a2[0].split(" to ")[0]]
        note_text = f"""{meeting}
{WEEK_START.strftime('%A, %B %d, %Y')}  |  10:0{mi} - 10:4{mi} AM  |  Zoom
Attendees: {', '.join(attendees)}

Discussion
- Pipeline is at ${1.72 + mi * 0.03:.2f}M with {18 + mi * 3} new leads this week.
- {COMPANIES[mi]} moved forward; {COMPANIES[mi + 5]} went quiet after the last touch.
- Inbound demo requests keep coming in — someone has to log them by hand.
- The weekly status email took most of Friday afternoon again.
- Nobody enjoys copying rows from the inbox into the spreadsheet.

Decisions
- Keep the Friday send time at 4:30pm.
- {a1[0]}.
- {a2[0]}.

Action items
- {a1[0]} — due {WEEK_DAYS[day]} EOD.
- {a2[0]} — due {WEEK_DAYS[(day + 1) % 5]}.
- Maya to compile follow-up notes and share with the group.

Parking lot
- Evaluate automating the status email next quarter.
- Look into a lead capture form for the website.
"""
        note_path.write_text(note_text, encoding="utf-8")
        pattern_c_note_ids.append(stem)

        eid = f"E{50 + mi:03d}"
        subject = FOLLOWUP_SUBJECTS[mi % len(FOLLOWUP_SUBJECTS)].format(meeting=meeting)
        body = FOLLOWUP_BODY_TEMPLATE.format(
            meeting=meeting,
            summary1=f"Pipeline at ${1.72 + mi * 0.03:.2f}M with {18 + mi * 3} new leads.",
            summary2=f"{COMPANIES[mi]} advanced; {COMPANIES[mi + 5]} needs a re-touch.",
            action1=a1[0],
            action2=a2[0],
        )
        emails.append(make_email(
            eid, day, 11 + mi, (mi * 13) % 60, maya,
            "team@brightloop.io", subject, body, "sent",
        ))
        pattern_c_email_ids.append(eid)

        for ai, (action, short) in enumerate((a1, a2)):
            tid = f"T{10 + mi * 2 + ai:03d}"
            due = (WEEK_START + timedelta(days=(day + ai) % 5)).strftime("%Y-%m-%d")
            tasks.append({
                "id": tid,
                "title": f"{short} (from {meeting})",
                "due": due,
                "status": "todo" if ai == 0 else "done",
                "project": "Meetings",
                "notes": f"Action item from {meeting} on {WEEK_DAYS[day]}.",
            })
            pattern_c_task_ids.append(tid)

    gt_patterns.append({
        "id": "C",
        "name": "Meeting follow-ups",
        "description": "After each meeting Maya manually writes a follow-up email and creates "
                       "tasks for the action items.",
        "minutes_per_occurrence": 15,
        "source_ids": pattern_c_note_ids + pattern_c_email_ids + pattern_c_task_ids,
        "kinds": ["note", "email", "task"],
    })

    # ------------------------------------------------------------------
    # Noise: newsletters, calendar invites, social chatter, internal updates
    # ------------------------------------------------------------------
    next_id = 70
    for i in range(6):
        nl = NEWSLETTERS[i % len(NEWSLETTERS)]
        eid = f"E{next_id:03d}"
        next_id += 1
        body = (
            f"{nl[1]}\n\nThis week we cover: {nl[1].lower()}, plus a teardown of a real "
            f"outbound sequence. Read time: 6 minutes.\n\n"
            f"Forward to a teammate who'd find this useful.\n\n"
            f"- The {nl[0]} team"
        )
        emails.append(make_email(
            eid, i % 5, 6 + (i % 4), (i * 11) % 60,
            email_addr(nl[0].replace(" ", ""), "newsletter.example.com"),
            maya, nl[1], body, "inbox",
        ))

    for i in range(5):
        eid = f"E{next_id:03d}"
        next_id += 1
        meeting = pick([
            "1:1 with Dana", "Pipeline sync", "All-hands", "Demo block", "Lunch & learn",
            "Interview debrief", "Customer call", "Product walkthrough", "Skip-level",
            "Quarterly planning",
        ])
        body = (
            f"Invitation\n\nWhen: {WEEK_DAYS[i % 5]}, Jan {6 + (i % 5)}, 2025, "
            f"{9 + (i % 8)}:00 AM - {10 + (i % 8)}:00 AM\n"
            f"Where: Zoom (link below)\n\n"
            f"You have been invited to {meeting}. Please accept or decline.\n\n"
            f"Zoom link: https://zoom.example.com/j/{100000000 + i}\n"
            f"Organizer: {pick(ALL_NAMES)}"
        )
        emails.append(make_email(
            eid, i % 5, 7 + (i % 9), (i * 13) % 60,
            "calendar@example.com", maya, f"Invitation: {meeting}", body, "inbox",
        ))

    for i in range(5):
        eid = f"E{next_id:03d}"
        next_id += 1
        quips = [
            "Congrats on the launch!",
            "This is huge - well done team.",
            "Sending this to my manager.",
            "Anyone else hitting this?",
        ]
        name = pick(ALL_NAMES)
        body = (
            f"{pick(ALL_NAMES)} and {pick(ALL_NAMES)} commented on a post you follow:\n\n"
            f"\"{pick(quips)}\"\n\n"
            f"View the thread or adjust your notifications."
        )
        emails.append(make_email(
            eid, i % 5, 12 + (i % 6), (i * 17) % 60,
            email_addr(name, "social.example.com"), maya,
            f"{name} mentioned you", body, "inbox",
        ))

    for i in range(7):
        eid = f"E{next_id:03d}"
        next_id += 1
        subj, snippet = PROJECT_UPDATES[i % len(PROJECT_UPDATES)]
        emails.append(make_email(
            eid, i % 5, 9 + (i % 9), (i * 19) % 60,
            email_addr(pick(ALL_NAMES), "brightloop.io"), maya,
            subj, snippet, "inbox",
        ))

    # ------------------------------------------------------------------
    # Two deliberate non-patterns (one-off work that should NOT be flagged)
    # ------------------------------------------------------------------
    eid = f"E{next_id:03d}"
    next_id += 1
    emails.append(make_email(
        eid, 4, 14, 0, email_addr("Dana Whitfield", "brightloop.io"), maya,
        "One-time: prep board deck numbers",
        "Maya — one-off ask: can you pull the pipeline numbers for the board deck by "
        "Monday? This is a one-time thing, not a recurring report. Thanks, Dana",
        "inbox",
    ))
    non_patterns.append({"id": eid, "kind": "email", "reason": "one-off board deck request, appears once"})

    eid = f"E{next_id:03d}"
    next_id += 1
    emails.append(make_email(
        eid, 2, 10, 30, email_addr("Riley Chen", "corevault.io"), maya,
        "Re: contract signature page",
        "Hi Maya — attaching the countersigned contract page. Just this once, please "
        "file it and confirm. No need for any process change. Thanks!\nRiley",
        "inbox",
    ))
    non_patterns.append({"id": eid, "kind": "email", "reason": "one-off contract filing request, appears once"})

    # ------------------------------------------------------------------
    # tasks.csv: 25 total (2 Pattern A + 10 Pattern C + 13 misc)
    # ------------------------------------------------------------------
    misc_tasks = [
        ("Update CRM stages for new deals", "2025-01-07", "done", "Sales Ops"),
        ("Rebuild the lead scoring model", "2025-01-08", "done", "Sales Ops"),
        ("Clean up duplicate accounts", "2025-01-09", "todo", "Sales Ops"),
        ("Book two customer reference calls", "2025-01-10", "todo", "Sales Ops"),
        ("Review SDR ramp metrics", "2025-01-09", "done", "Sales Ops"),
        ("Share competitor battlecards", "2025-01-08", "todo", "Marketing"),
        ("Refresh demo environment data", "2025-01-10", "todo", "Sales Ops"),
        ("Close out Q4 forecast gaps", "2025-01-07", "done", "Finance"),
        ("Document the follow-up checklist", "2025-01-10", "todo", "Sales Ops"),
        ("Audit webhook failures", "2025-01-09", "todo", "Engineering"),
        ("Draft the partner one-pager", "2025-01-07", "todo", "Partnerships"),
        ("Schedule the pricing review", "2025-01-08", "done", "Finance"),
        ("File the signed Corevault contract", "2025-01-10", "todo", "Legal"),
    ]
    for i, (title, due, status, project) in enumerate(misc_tasks):
        tid = f"T{30 + i:03d}"
        tasks.append({
            "id": tid,
            "title": title,
            "due": due,
            "status": status,
            "project": project,
            "notes": "",
        })
    non_patterns.append({
        "id": "T042",
        "kind": "task",
        "reason": "one-off contract filing task, appears once",
    })

    # ------------------------------------------------------------------
    # leads.csv: 30 rows with messy dates, missing fields, mixed sources
    # ------------------------------------------------------------------
    lead_rows: list[dict[str, str]] = []
    base_lead_companies = [
        ("Acme Robotics", "contact", "website"),
        ("Bloom Analytics", "contact", "webinar"),
        ("Cascade Retail", "contact", "referral"),
    ]
    for i in range(30):
        company = COMPANIES[i % len(COMPANIES)]
        # vary the company slightly so repeats don't collide
        if i >= len(COMPANIES):
            company = f"{company} {['LLC', 'Inc', 'Group'][i % 3]}"
        contact = ALL_NAMES[i % len(ALL_NAMES)]
        addr = email_addr(contact, company.lower().replace(" ", "").replace(".", "") + ".com")

        # Inconsistent date formats (this is deliberate noise)
        created_dt = WEEK_START - timedelta(days=rng.randint(0, 10))
        date_style = i % 4
        if date_style == 0:
            created = created_dt.strftime("%Y-%m-%d")
        elif date_style == 1:
            created = created_dt.strftime("%m/%d/%Y")
        elif date_style == 2:
            created = created_dt.strftime("%d-%b-%Y")
        else:
            created = created_dt.strftime("%b %d, %Y")

        source = rng.choice(["website", "webinar", "referral", "tradeshow", "manual", ""])
        status = rng.choice(["new", "contacted", "qualified", "demo set", "nurture"])

        row = {
            "id": f"L{i + 1:03d}",
            "created": created,
            "company": company,
            "contact": contact,
            "email": addr,
            "source": source,
            "status": status,
            "notes": "",
        }
        # Deliberate missing fields (empty strings)
        if i % 7 == 3:
            row["contact"] = ""
        if i % 11 == 5:
            row["email"] = ""
        if i % 13 == 9:
            row["source"] = ""
        lead_rows.append(row)

    # ------------------------------------------------------------------
    # Ground truth
    # ------------------------------------------------------------------
    ground_truth = {
        "persona": "Maya Rao, sales operations manager at a 30-person B2B SaaS company",
        "generated_at": datetime(2025, 1, 10, 18, 0, 0).isoformat(),
        "seed": SEED,
        "patterns": gt_patterns,
        "non_patterns": non_patterns,
        "expected_counts": {
            "emails": len(emails),
            "leads": len(lead_rows),
            "tasks": len(tasks),
            "notes": len(list((OUT_DIR / "meeting_notes").glob("*.txt"))),
        },
    }

    # ------------------------------------------------------------------
    # Write files
    # ------------------------------------------------------------------
    with (OUT_DIR / "emails.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "date", "from", "to", "subject", "body", "labels"])
        writer.writeheader()
        writer.writerows(emails)

    with (OUT_DIR / "leads.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "created", "company", "contact", "email", "source", "status", "notes"])
        writer.writeheader()
        writer.writerows(lead_rows)

    with (OUT_DIR / "tasks.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "title", "due", "status", "project", "notes"])
        writer.writeheader()
        writer.writerows(tasks)

    (OUT_DIR / "GROUND_TRUTH.json").write_text(
        json.dumps(ground_truth, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"emails: {len(emails)}  leads: {len(lead_rows)}  tasks: {len(tasks)}  "
          f"notes: {len(list((OUT_DIR / 'meeting_notes').glob('*.txt')))}")
    print(f"patterns: {len(gt_patterns)}  non-patterns: {len(non_patterns)}")
    print(f"written to {OUT_DIR}")


if __name__ == "__main__":
    main()
