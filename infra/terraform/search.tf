locals {
  debian_image = "projects/debian-cloud/global/images/family/debian-12"
}

resource "google_compute_address" "search" {
  name         = "${var.name}-search"
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = google_compute_subnetwork.main.id
}

resource "google_compute_disk" "search_data" {
  name = "${var.name}-search-data"
  type = "pd-ssd"
  size = var.search_disk_gb
  zone = var.zone
}

resource "google_compute_resource_policy" "daily_snapshots" {
  name   = "${var.name}-daily-snapshots"
  region = var.region

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        start_time    = "04:00"
      }
    }
    retention_policy {
      max_retention_days    = 7
      on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"
    }
  }
}

resource "google_compute_disk_resource_policy_attachment" "search_snapshots" {
  name = google_compute_resource_policy.daily_snapshots.name
  disk = google_compute_disk.search_data.name
  zone = var.zone
}

resource "google_compute_instance" "search" {
  name           = "${var.name}-search"
  machine_type   = var.search_machine_type
  zone           = var.zone
  can_ip_forward = false

  boot_disk {
    initialize_params {
      image = local.debian_image
      size  = 20
    }
  }

  attached_disk {
    source      = google_compute_disk.search_data.id
    device_name = "data"
  }

  network_interface {
    subnetwork = google_compute_subnetwork.main.id
    network_ip = google_compute_address.search.address
  }

  service_account {
    email  = google_service_account.search.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot = false
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/templates/search-startup.sh.tftpl", {
    elastic_password_secret = google_secret_manager_secret.secrets["elastic-password"].secret_id
    api_key_secret          = google_secret_manager_secret.secrets["elastic-api-key"].secret_id
    elasticsearch_version   = var.elasticsearch_version
    heap_gb                 = var.search_heap_gb
  })

  depends_on = [
    google_secret_manager_secret_version.elastic_password,
    google_secret_manager_secret_iam_member.access,
  ]
}
