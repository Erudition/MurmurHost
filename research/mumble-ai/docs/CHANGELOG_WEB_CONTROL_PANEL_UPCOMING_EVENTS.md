# Web Control Panel - Upcoming Events Display

**Date:** October 9, 2025
**Status:** ✅ Deployed

---

## Summary of Changes

Enhanced the web control panel to display upcoming schedule events in two locations:
1. **Main Dashboard** - Shows next 7 days of upcoming events
2. **Schedule Page** - Shows list view of next 30 days below the calendar

---

## New Features

### 1. Main Dashboard - Upcoming Events Section

**Location:** Main page (index.html) below statistics cards

**Features:**
- Displays up to 5 upcoming events from the next 7 days
- Color-coded importance badges:
  - 🔴 **Critical** (8-10): Red border and badge
  - 🟠 **High** (5-7): Orange border and badge
  - 🔵 **Normal** (1-4): Blue border and badge
- Shows event title, user, date, time, and description
- Auto-refreshes every 30 seconds
- "View All →" link to schedule page
- Hover animations for better UX

**Empty State:**
- Shows message when no upcoming events exist

### 2. Schedule Page - List View Below Calendar

**Location:** Schedule page (schedule.html) below the calendar

**Features:**
- Displays up to 20 upcoming events from the next 30 days
- Same color-coded importance system as main dashboard
- Clickable event items that open the edit modal
- Shows full event details including:
  - 👤 User name
  - 📅 Date with day of week
  - 🕐 Time (if specified)
  - 📝 Description (if specified)
- Respects user filter selection
- Automatically refreshes when:
  - User filter changes
  - Event is added/edited/deleted
  - Calendar is manually refreshed

---

## Technical Implementation

### Backend Changes

#### New API Endpoint

**`GET /api/schedule/upcoming`**

**Parameters:**
- `days` (optional, default: 7) - Number of days ahead to fetch
- `limit` (optional, default: 10) - Maximum events to return
- `user` (optional) - Filter by specific user

**Query:**
```sql
SELECT id, user_name, title, event_date, event_time, description, importance, created_at
FROM schedule_events
WHERE active = TRUE
  AND event_date >= CURRENT_DATE
  AND event_date <= CURRENT_DATE + INTERVAL 'N days'
  [AND user_name = 'username']
ORDER BY event_date, event_time
LIMIT N
```

**Response:**
```json
[
  {
    "id": 1,
    "user_name": "Charles",
    "title": "Doctor Appointment",
    "event_date": "2025-10-15",
    "event_time": "14:30:00",
    "description": "Annual checkup",
    "importance": 7,
    "created_at": "2025-10-09T10:00:00"
  }
]
```

### Frontend Changes

#### Main Dashboard (index.html)

**New CSS Classes:**
```css
.upcoming-events           /* Container styling */
.upcoming-events-list      /* Event list layout */
.event-item                /* Individual event card */
.event-item.high-importance    /* Orange styling */
.event-item.critical-importance /* Red styling */
.event-info                /* Event details container */
.event-title               /* Event title text */
.event-details             /* Event metadata */
.event-badge               /* Importance badge */
.event-badge.normal        /* Blue badge */
.event-badge.high          /* Orange badge */
.event-badge.critical      /* Red badge */
.no-events                 /* Empty state message */
.view-all-link             /* Link to schedule page */
```

**JavaScript Function:**
```javascript
async function loadUpcomingEvents() {
    // Fetches from /api/schedule/upcoming?days=7&limit=5
    // Renders events with color-coding
    // Shows empty state if no events
}
```

**Auto-refresh:**
```javascript
setInterval(loadUpcomingEvents, 30000); // Every 30 seconds
```

#### Schedule Page (schedule.html)

**New CSS Classes:**
```css
.events-list-container     /* List view container */
.events-list               /* Event list layout */
.list-event-item           /* Individual list item */
.list-event-item.normal-importance   /* Blue styling */
.list-event-item.high-importance     /* Orange styling */
.list-event-item.critical-importance /* Red styling */
.list-event-info           /* Event info container */
.list-event-title          /* Event title text */
.list-event-details        /* Event metadata with emojis */
.list-event-badge          /* Importance badge */
.no-list-events            /* Empty state message */
```

**JavaScript Functions:**
```javascript
async function loadEventsList() {
    // Fetches from /api/schedule/upcoming?days=30&limit=20
    // Respects user filter
    // Renders clickable event items
}

function openEditEventById(eventId) {
    // Finds event in calendar and opens edit modal
}
```

**Integration Points:**
- Called on page load via `DOMContentLoaded`
- Called when user filter changes
- Called when event is added/edited/deleted
- Called when calendar is manually refreshed

---

## Files Modified

### Backend

**web-control-panel/app.py**

**Lines 1112-1154:** Added `get_upcoming_events()` endpoint
- Accepts `days`, `limit`, and `user` parameters
- Filters by date range and user
- Returns upcoming events sorted by date/time

### Frontend

**web-control-panel/templates/index.html**

**Lines 237-338:** Added CSS for upcoming events section
- Event card styling with color-coding
- Badge styling for importance levels
- Hover animations

**Lines 370-379:** Added HTML for upcoming events section
- Container with header and "View All" link
- Event list container

**Lines 648:** Added `loadUpcomingEvents()` call to page initialization

**Lines 652:** Added auto-refresh interval (30 seconds)

**Lines 669-716:** Added `loadUpcomingEvents()` function
- Fetches upcoming events from API
- Renders with color-coded styling
- Shows empty state when appropriate

**web-control-panel/templates/schedule.html**

**Lines 268-363:** Added CSS for list view
- List item styling with color-coding
- Badge styling
- Hover effects and cursor pointer

**Lines 386-392:** Added HTML for list view section
- Container below calendar
- Event list container

**Lines 447:** Added `loadEventsList()` call to page initialization

**Lines 485-488:** Updated user filter change handler
- Now refreshes both calendar and list view

**Lines 533-585:** Added `loadEventsList()` function
- Fetches upcoming events with user filter
- Renders clickable event items
- Shows full event details with emojis

**Lines 587-593:** Added `openEditEventById()` function
- Finds event by ID and opens edit modal

**Lines 673, 697, 707:** Updated refresh calls
- Calendar saves now refresh list view
- Delete operations now refresh list view
- Manual refresh now refreshes list view

---

## User Interface

### Main Dashboard View

```
┌───────────────────────────────────────────────────┐
│ 📅 Upcoming Events (Next 7 Days)   View All →    │
├───────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────┐  │
│ │ Doctor Appointment              [HIGH]      │  │
│ │ Charles • Oct 15, 2025 at 14:30             │  │
│ └─────────────────────────────────────────────┘  │
│ ┌─────────────────────────────────────────────┐  │
│ │ Team Meeting                    [NORMAL]    │  │
│ │ Alice • Oct 16, 2025 at 10:00               │  │
│ └─────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

### Schedule Page List View

```
┌───────────────────────────────────────────────────┐
│ 📋 Upcoming Events (Next 30 Days)                 │
├───────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────┐  │
│ │ Dentist Appointment                         │  │
│ │ 👤 Bob • 📅 Mon, Oct 14, 2025 at 09:00     │  │
│ │ 📝 Regular cleaning          [NORMAL]       │  │
│ └─────────────────────────────────────────────┘  │
│ ┌─────────────────────────────────────────────┐  │
│ │ Project Deadline                            │  │
│ │ 👤 Team • 📅 Wed, Oct 16, 2025             │  │
│ │ 📝 Submit final report       [CRITICAL]     │  │
│ └─────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

---

## Color Coding System

### Importance Levels

**Normal (1-4):**
- Border: Blue (#667eea)
- Badge: Light blue background (#dbeafe), dark blue text (#1e40af)
- Use: Regular appointments and events

**High (5-7):**
- Border: Orange (#f97316)
- Badge: Light orange background (#fed7aa), dark orange text (#c2410c)
- Use: Important meetings and deadlines

**Critical (8-10):**
- Border: Red (#ef4444)
- Badge: Light red background (#fee2e2), dark red text (#991b1b)
- Use: Urgent appointments and critical deadlines

---

## Deployment

### Build and Deploy Commands

```bash
# Build new image
docker-compose build --no-cache web-control-panel

# Deploy updated container
docker-compose stop web-control-panel
docker-compose rm -f web-control-panel
docker-compose up -d web-control-panel

# Verify deployment
docker-compose logs --tail=20 web-control-panel
```

### Verification Steps

```bash
# Check container is running
docker-compose ps web-control-panel

# Test API endpoint
curl http://localhost:5002/api/schedule/upcoming?days=7&limit=5

# Open web interface
# Navigate to http://localhost:5002
# Verify upcoming events section appears on main page
# Navigate to Schedule Manager
# Verify list view appears below calendar
```

---

## Benefits

### User Experience
- **Quick overview** - See upcoming events without navigating away
- **At-a-glance priority** - Color-coded importance levels
- **Easy access** - Click to edit from list view
- **Real-time updates** - Auto-refresh keeps data current
- **Flexible filtering** - User filter applies to both calendar and list

### Dashboard Integration
- **Contextual information** - Events visible alongside stats
- **Improved navigation** - Direct link to full schedule
- **Better awareness** - Users see what's coming up immediately

### Schedule Page Enhancement
- **Dual view** - Calendar for visual planning, list for details
- **Extended range** - See 30 days ahead in list view
- **Interactive** - Click any event to edit
- **Comprehensive details** - All event info visible at once

---

## Performance

### Auto-Refresh Intervals
- **Main Dashboard:** Every 30 seconds
- **Statistics:** Every 10 seconds (existing)

### API Optimization
- Limit results to prevent large payloads
- Filter at database level for efficiency
- Use indexed columns (event_date) for fast queries

---

## Future Enhancements

Possible future improvements:
- [ ] Add date range selector for list view
- [ ] Export upcoming events to calendar file (.ics)
- [ ] Add notification badges for events happening today
- [ ] Group events by date in list view
- [ ] Add search/filter within list view
- [ ] Show countdown timer for imminent events
- [ ] Add "Mark as Complete" button for past events

---

## Testing Checklist

- [x] Main dashboard shows upcoming events
- [x] Color-coding works correctly
- [x] Auto-refresh updates every 30 seconds
- [x] "View All" link navigates to schedule
- [x] Schedule list view displays events
- [x] List view respects user filter
- [x] Clicking event opens edit modal
- [x] Adding event refreshes list
- [x] Editing event refreshes list
- [x] Deleting event refreshes list
- [x] Manual refresh updates list
- [x] Empty states display correctly
- [x] API endpoint supports user filtering
- [x] Importance badges display correctly

---

## Related Documentation

- **Architecture**: `docs/ARCHITECTURE.md`
- **Configuration**: `docs/CONFIGURATION.md`
- **Email Summary Enhancements**: `docs/CHANGELOG_EMAIL_SUMMARY_ENHANCEMENTS.md`
- **Deployment Summary**: `docs/DEPLOYMENT_SUMMARY_2025-10-09.md`

---

## Summary

**What Changed:**
- Added API endpoint for upcoming events with user filtering
- Created upcoming events section on main dashboard
- Added list view below calendar on schedule page
- Integrated list view with user filter and calendar operations
- Added color-coded importance indicators throughout

**Result:**
- Upcoming events visible on main dashboard ✅
- Comprehensive list view on schedule page ✅
- Auto-refresh keeps data current ✅
- Color-coded priority system ✅
- Interactive list with edit capability ✅

**Deployed:** October 9, 2025, 09:50 UTC

The web control panel now provides quick access to upcoming events from both the main dashboard and the schedule page with an enhanced list view.
