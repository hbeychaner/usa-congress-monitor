resource "google_artifact_registry_repository" "images" {
  repository_id = var.name
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "random_password" "elastic" {
  length  = 32
  special = false
}

resource "random_password" "rabbitmq" {
  length  = 32
  special = false
}

locals {
  secret_ids = toset([
    "congress-api-key",
    "elastic-password",
    "elastic-api-key",
    "rabbitmq-password",
    "rabbitmq-url",
  ])
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = local.secret_ids
  secret_id = "${var.name}-${each.value}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "congress_api_key" {
  secret      = google_secret_manager_secret.secrets["congress-api-key"].id
  secret_data = var.congress_api_key
}

resource "google_secret_manager_secret_version" "elastic_password" {
  secret      = google_secret_manager_secret.secrets["elastic-password"].id
  secret_data = random_password.elastic.result
}

resource "google_secret_manager_secret_version" "rabbitmq_password" {
  secret      = google_secret_manager_secret.secrets["rabbitmq-password"].id
  secret_data = random_password.rabbitmq.result
}

# Cloud Run reaches the broker on the worker VM's private address.
resource "google_secret_manager_secret_version" "rabbitmq_url" {
  secret      = google_secret_manager_secret.secrets["rabbitmq-url"].id
  secret_data = "amqp://${var.name}:${random_password.rabbitmq.result}@${google_compute_address.worker.address}:5672/"
}

# The search VM creates the app API key at first boot and stores it in elastic-api-key.
