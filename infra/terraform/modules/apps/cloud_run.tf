locals {
  secret_env = {
    ES_LOCAL_API_KEY = var.secret_ids["elastic_api_key"]
    RABBITMQ_URL     = var.secret_ids["rabbitmq_url"]
    CONGRESS_API_KEY = var.secret_ids["congress_api_key"]
  }
}

# Reachable only through the load balancer; IAP authenticates users there.
resource "google_cloud_run_v2_service" "api" {
  name                 = "${var.name}-api"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  invoker_iam_disabled = true
  deletion_protection  = false

  template {
    service_account = var.api_service_account

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = 5
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = var.network
        subnetwork = var.subnetwork
      }
    }

    containers {
      image = var.backend_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "ES_LOCAL_URL"
        value = var.es_url
      }

      env {
        name  = "REDIS_URL"
        value = var.redis_url
      }

      dynamic "env" {
        for_each = local.secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service" "frontend" {
  name                 = "${var.name}-frontend"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  invoker_iam_disabled = true
  deletion_protection  = false

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.frontend_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }
    }
  }
}
