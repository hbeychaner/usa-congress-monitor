locals {
  registry       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
  backend_image  = "${local.registry}/backend:${var.image_tag}"
  frontend_image = "${local.registry}/frontend:${var.image_tag}"
  es_url         = "http://${google_compute_address.search.address}:9200"
  redis_url      = "redis://${google_compute_address.worker.address}:6379/0"
}

resource "google_compute_address" "worker" {
  name         = "${var.name}-worker"
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = google_compute_subnetwork.main.id
}

resource "google_compute_disk" "worker_data" {
  name = "${var.name}-worker-data"
  type = "pd-balanced"
  size = var.worker_disk_gb
  zone = var.zone
}

resource "google_compute_disk_resource_policy_attachment" "worker_snapshots" {
  name = google_compute_resource_policy.daily_snapshots.name
  disk = google_compute_disk.worker_data.name
  zone = var.zone
}

# Runs Celery workers and beat plus RabbitMQ and Redis; holds the jobs ledger, status files and build logs.
resource "google_compute_instance" "worker" {
  name         = "${var.name}-worker"
  machine_type = var.worker_machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = local.debian_image
      size  = 20
    }
  }

  attached_disk {
    source      = google_compute_disk.worker_data.id
    device_name = "data"
  }

  network_interface {
    subnetwork = google_compute_subnetwork.main.id
    network_ip = google_compute_address.worker.address
  }

  service_account {
    email  = google_service_account.worker.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
    worker-compose = file("${path.module}/../../deploy/gcp/docker-compose.worker.yml")
  }

  metadata_startup_script = templatefile("${path.module}/templates/worker-startup.sh.tftpl", {
    region                   = var.region
    backend_image            = local.backend_image
    es_url                   = local.es_url
    rabbitmq_user            = var.name
    rabbitmq_password_secret = google_secret_manager_secret.secrets["rabbitmq-password"].secret_id
    congress_api_key_secret  = google_secret_manager_secret.secrets["congress-api-key"].secret_id
    es_api_key_secret        = google_secret_manager_secret.secrets["elastic-api-key"].secret_id
  })

  depends_on = [
    google_secret_manager_secret_version.rabbitmq_password,
    google_secret_manager_secret_version.congress_api_key,
    google_secret_manager_secret_iam_member.access,
    google_project_iam_member.project,
  ]
}
