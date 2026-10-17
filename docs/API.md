# API summary
Interactive, always-current docs: run the backend and open `/docs` (Swagger) or `/openapi.json`. Auth: `Authorization: Bearer <JWT>` from `/api/auth/login`. Errors: `{"detail": "..."}` or `{"errors": [...]}` (422).

| Area | Endpoints | Roles |
|---|---|---|
| Auth | `POST /api/auth/register`, `/register-club`, `/login`; `GET/PATCH /api/auth/me` | public / any |
| Discovery | `GET /api/events?q&category_id&club_id&date_from&date_to&sort&page&page_size`, `GET /api/events/{id}`, `GET /api/meta` | public |
| Student | `POST/DELETE /api/events/{id}/register`, `POST/DELETE /api/events/{id}/bookmark`, `GET /api/me/registrations`, `/api/me/bookmarks`, `GET /api/registrations/{id}/qr.png`, `/certificate`, `POST /api/events/{id}/feedback` | student |
| Organizer | `GET /api/events/manage`, `POST /api/events`, `PUT /api/events/{id}`, `POST /api/events/{id}/submit|cancel|poster`, `GET /api/events/{id}/attendees(.csv)|feedback`, `POST /api/checkin` | club (own), admin |
| Approval | `POST /api/events/{id}/approve|reject` | admin |
| CSV import | `GET /api/imports/template.csv`, `POST /api/imports/preview|commit`, `GET /api/imports/jobs`, `/jobs/{id}/errors(.csv)` | club, admin |
| Admin | `/api/admin/users`, `/clubs/{id}`, `/venues`, `/categories`, `/audit`, `/analytics`, `/reports/{events|registrations|attendance}.csv` | admin |
| Notifications | `GET /api/notifications`, `POST /api/notifications/read-all` | any |
| Ops | `GET /api/health` | public |

Event states: `draft → pending_approval → published → completed`, plus `rejected` and `cancelled`. Registration states: `registered | waitlisted | cancelled`.
