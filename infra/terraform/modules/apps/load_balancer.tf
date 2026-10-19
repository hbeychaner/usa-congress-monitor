locals {
  services = {
    api      = google_cloud_run_v2_service.api.name
    frontend = google_cloud_run_v2_service.frontend.name
  }

  # Paths served by the API; everything else is the single-page app.
  api_paths = ["/api/*", "/health", "/docs", "/redoc", "/openapi.json"]
}

resource "google_compute_global_address" "lb" {
  name = "${var.name}-lb"
}

resource "google_compute_region_network_endpoint_group" "serverless" {
  for_each              = local.services
  name                  = "${var.name}-${each.key}"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = each.value
  }
}

# IAP uses the Google-managed OAuth client; the project needs an OAuth consent screen.
resource "google_compute_backend_service" "serverless" {
  for_each              = local.services
  name                  = "${var.name}-${each.key}"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 120

  backend {
    group = google_compute_region_network_endpoint_group.serverless[each.key].id
  }

  iap {
    enabled = true
  }

  log_config {
    enable = true
  }
}

resource "google_iap_web_backend_service_iam_member" "access" {
  for_each = {
    for pair in setproduct(keys(local.services), var.iap_members) :
    "${pair[0]}-${pair[1]}" => { service = pair[0], member = pair[1] }
  }

  web_backend_service = google_compute_backend_service.serverless[each.value.service].name
  role                = "roles/iap.httpsResourceAccessor"
  member              = each.value.member
}

resource "google_compute_url_map" "https" {
  name            = "${var.name}-https"
  default_service = google_compute_backend_service.serverless["frontend"].id

  host_rule {
    hosts        = [var.domain]
    path_matcher = "app"
  }

  path_matcher {
    name            = "app"
    default_service = google_compute_backend_service.serverless["frontend"].id

    path_rule {
      paths   = local.api_paths
      service = google_compute_backend_service.serverless["api"].id
    }
  }
}

resource "google_compute_managed_ssl_certificate" "main" {
  name = "${var.name}-cert"

  managed {
    domains = [var.domain]
  }
}

resource "google_compute_target_https_proxy" "main" {
  name             = "${var.name}-https"
  url_map          = google_compute_url_map.https.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main.id]
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${var.name}-https"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb.id
  port_range            = "443"
  target                = google_compute_target_https_proxy.main.id
}

resource "google_compute_url_map" "redirect" {
  name = "${var.name}-redirect"

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "redirect" {
  name    = "${var.name}-http"
  url_map = google_compute_url_map.redirect.id
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${var.name}-http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb.id
  port_range            = "80"
  target                = google_compute_target_http_proxy.redirect.id
}
