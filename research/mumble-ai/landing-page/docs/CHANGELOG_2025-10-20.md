## 2025-10-20 — Consolidated Changelog

### Overview
- Introduces a comprehensive Smart Memory Dashboard in the web control panel and Flutter app
- Expands Memory System APIs and client handling for mixed/legacy response formats
- Adds database schema to support entity tracking, memory consolidation logs, and richer persistent memories
- Improves error handling, logging, and UX across mobile and web

### Web Control Panel (`web-control-panel/templates/index.html`)
- New Memory System Dashboard UI:
  - Status cards for Redis, ChromaDB, PostgreSQL, Entity Intelligence, and Consolidation
  - Search interface for conversations and entities
  - Entity list with pagination
  - Consolidation history and summary stats
  - Persistent memories view with filters, add/delete, and quick refresh

### Flutter App (`mumble_ai_flutter/`)
- Routing update (`lib/main.dart`): adds `/memory-system` route
- New screens and widgets:
  - `lib/screens/memory_system_screen.dart`: full Memory System dashboard (Overview, Entities, Consolidation, Search, Stats)
  - `lib/screens/memories_screen.dart`: enhanced to support wrapped and legacy API responses; improved filtering and actions
  - `lib/widgets/memory_search_bar.dart`: debounced search with type filter (conversations/entities/all)
  - `lib/widgets/search_result_card.dart`: unified presentation for search results
  - `lib/widgets/entity_card.dart`: entity display with actions and metadata
  - `lib/widgets/app_drawer.dart`: adds Memory System entry, version/about, and quick navigation
- API service improvements (`lib/services/api_service.dart`):
  - Consistent timeouts and optional debug logging
  - Safer response casting helpers; better error mapping for new backend error format
  - Memory System endpoints: status, entities (CRUD), consolidation, context, stats
  - Extended chat timeout via dedicated client
- Constants update (`lib/utils/constants.dart`): new endpoints, entity/search taxonomies, and defaults

### Database (`init-db.sql`)
- Adds/extends schema to support Smart Memory features:
  - `conversation_sessions` with activity tracking
  - `conversation_history` with embeddings, importance, consolidation markers, indices, and view
  - `persistent_memories` with tags, importance, event_date/time, embedding, indices and active view
  - `entity_mentions` for entity tracking with canonical IDs and indices
  - `memory_consolidation_log` for consolidation runs and indices
  - Additional indices for performance across conversations, memories, schedule, and email logs
  - `cosine_similarity` function for embeddings
  - Seeded `bot_config` keys for memory system configuration (ChromaDB, Redis, consolidation settings, weights)

### Bot & Bridge (summary)
- Smart Memory system integration points in `mumble-bot/memory_manager.py`:
  - Embedding generation via Ollama, hybrid search (semantic + keyword), session cache updates
  - Entity extraction and canonicalization, storage to ChromaDB and Postgres
  - Consolidation job orchestration with periodic runs and summarization
- SIP bridge and email summary service received updates (notable for memory and status UIs), with improved error handling/logging (see commit diff for details)

### Backward Compatibility
- Flutter and web clients handle both wrapped `{ success, data }` and legacy array responses for selected endpoints (users, memories, search)

### Migration & Upgrade Notes
1. Database
   - Apply `init-db.sql` to add new tables, functions, and indices
   - Existing databases are protected via `IF NOT EXISTS` guards; event_date/time columns added conditionally
2. Configuration
   - Ensure new `bot_config` keys exist (seeded by `init-db.sql`); verify `chromadb_url`, `redis_url`, and model names
3. Services
   - Rebuild/restart stack after schema changes:
     - `docker-compose build --no-cache` (if needed)
     - `docker-compose up -d`
4. Health Checks
   - Verify `http://localhost:5002/api/memory/status` returns healthy statuses for Redis/ChromaDB/Postgres

### Testing
- Web Control Panel
  - Navigate to Memory System Dashboard
  - Confirm status cards populate and auto-refresh
  - Run searches and verify results across conversations and entities
  - Add and delete a persistent memory; verify in DB and UI
- Flutter App
  - Open Memories and Memory System screens; validate filters, search, entity CRUD, and stats
  - Verify error messages are user-friendly on timeouts and API errors
- Database
  - Confirm tables and indices exist; run basic queries for recent conversations and active memories

### Known Limitations
- Consolidated memories retrieval placeholder remains in-memory in some code paths; ensure vector-store retrieval is wired if needed
- Large responses may require pagination tuning in clients

### Credits
- Smart Memory UI/UX improvements across web and Flutter

