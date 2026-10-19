output "artifact_registry" {
  value = local.registry
}

output "dns_a_record" {
  description = "Point an A record for var.domain at this address (empty until deploy_apps is true)."
  value       = one(module.apps[*].lb_ip_address)
}

output "search_internal_url" {
  value = local.es_url
}

output "worker_vm" {
  value = google_compute_instance.worker.name
}

output "search_vm" {
  value = google_compute_instance.search.name
}
