module "apps" {
  count  = var.deploy_apps ? 1 : 0
  source = "./modules/apps"

  project_id          = var.project_id
  region              = var.region
  name                = var.name
  domain              = var.domain
  iap_members         = var.iap_members
  network             = google_compute_network.main.name
  subnetwork          = google_compute_subnetwork.main.name
  backend_image       = local.backend_image
  frontend_image      = local.frontend_image
  api_service_account = google_service_account.api.email
  api_min_instances   = var.api_min_instances
  es_url              = local.es_url
  redis_url           = local.redis_url

  secret_ids = {
    elastic_api_key  = google_secret_manager_secret.secrets["elastic-api-key"].secret_id
    rabbitmq_url     = google_secret_manager_secret.secrets["rabbitmq-url"].secret_id
    congress_api_key = google_secret_manager_secret.secrets["congress-api-key"].secret_id
  }

  depends_on = [
    google_secret_manager_secret_version.rabbitmq_url,
    google_secret_manager_secret_version.congress_api_key,
    google_secret_manager_secret_iam_member.access,
    google_project_iam_member.project,
    google_compute_instance.search,
  ]
}
