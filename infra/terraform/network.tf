resource "google_compute_network" "main" {
  name                    = var.name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "main" {
  name                     = var.name
  region                   = var.region
  network                  = google_compute_network.main.id
  ip_cidr_range            = "10.10.0.0/24"
  private_ip_google_access = true
}

resource "google_compute_router" "main" {
  name    = var.name
  region  = var.region
  network = google_compute_network.main.id
}

# VMs have no public IPs; NAT gives them outbound access to the Congress API and package mirrors.
resource "google_compute_router_nat" "main" {
  name                               = var.name
  router                             = google_compute_router.main.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# Cloud Run (Direct VPC egress) and the VMs all live in this subnet.
resource "google_compute_firewall" "internal" {
  name          = "${var.name}-internal"
  network       = google_compute_network.main.name
  direction     = "INGRESS"
  source_ranges = [google_compute_subnetwork.main.ip_cidr_range]

  allow {
    protocol = "tcp"
    ports    = ["9200", "5672", "6379"]
  }
}

resource "google_compute_firewall" "iap_ssh" {
  name          = "${var.name}-iap-ssh"
  network       = google_compute_network.main.name
  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
