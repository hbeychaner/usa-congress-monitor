resource "google_service_account" "api" {
  account_id   = "${var.name}-api"
  display_name = "Congress Tracker API (Cloud Run)"
}

resource "google_service_account" "worker" {
  account_id   = "${var.name}-worker"
  display_name = "Congress Tracker workers (VM)"
}

resource "google_service_account" "search" {
  account_id   = "${var.name}-search"
  display_name = "Congress Tracker search (VM)"
}

locals {
  project_roles = {
    api_vertex      = { member = google_service_account.api.member, role = "roles/aiplatform.user" }
    worker_vertex   = { member = google_service_account.worker.member, role = "roles/aiplatform.user" }
    worker_registry = { member = google_service_account.worker.member, role = "roles/artifactregistry.reader" }
    worker_logs     = { member = google_service_account.worker.member, role = "roles/logging.logWriter" }
    worker_metrics  = { member = google_service_account.worker.member, role = "roles/monitoring.metricWriter" }
    search_logs     = { member = google_service_account.search.member, role = "roles/logging.logWriter" }
    search_metrics  = { member = google_service_account.search.member, role = "roles/monitoring.metricWriter" }
  }

  secret_access = {
    api_es_key         = { member = google_service_account.api.member, secret = "elastic-api-key", role = "roles/secretmanager.secretAccessor" }
    api_rabbitmq_url   = { member = google_service_account.api.member, secret = "rabbitmq-url", role = "roles/secretmanager.secretAccessor" }
    api_congress_key   = { member = google_service_account.api.member, secret = "congress-api-key", role = "roles/secretmanager.secretAccessor" }
    worker_es_key      = { member = google_service_account.worker.member, secret = "elastic-api-key", role = "roles/secretmanager.secretAccessor" }
    worker_rabbitmq    = { member = google_service_account.worker.member, secret = "rabbitmq-password", role = "roles/secretmanager.secretAccessor" }
    worker_congress    = { member = google_service_account.worker.member, secret = "congress-api-key", role = "roles/secretmanager.secretAccessor" }
    search_password    = { member = google_service_account.search.member, secret = "elastic-password", role = "roles/secretmanager.secretAccessor" }
    search_publish_key = { member = google_service_account.search.member, secret = "elastic-api-key", role = "roles/secretmanager.secretVersionManager" }
  }
}

resource "google_project_iam_member" "project" {
  for_each = local.project_roles
  project  = var.project_id
  role     = each.value.role
  member   = each.value.member
}

resource "google_secret_manager_secret_iam_member" "access" {
  for_each  = local.secret_access
  secret_id = google_secret_manager_secret.secrets[each.value.secret].id
  role      = each.value.role
  member    = each.value.member
}
