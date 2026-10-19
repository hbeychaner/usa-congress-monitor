variable "project_id" {
  type        = string
  description = "GCP project that hosts the deployment."
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "name" {
  type        = string
  default     = "congress"
  description = "Prefix for resource names."
}

variable "domain" {
  type        = string
  default     = "congress.example.com"
  description = "Public hostname served by the load balancer. Placeholder until a real domain exists."
}

variable "iap_members" {
  type        = list(string)
  description = "IAM members allowed through Google sign-in, e.g. user:you@gmail.com, group:team@corp.com, domain:corp.com."
}

variable "deploy_apps" {
  type        = bool
  default     = false
  description = "Create Cloud Run, the load balancer and IAP. Enable after images are pushed and the search VM has published its API key."
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "congress_api_key" {
  type        = string
  sensitive   = true
  description = "api.congress.gov key used by the ingest workers."
}

variable "api_min_instances" {
  type    = number
  default = 0
}

variable "search_machine_type" {
  type    = string
  default = "e2-standard-4"
}

variable "search_heap_gb" {
  type        = number
  default     = 8
  description = "Elasticsearch JVM heap; keep at or below half of the VM memory."
}

variable "search_disk_gb" {
  type    = number
  default = 200
}

variable "elasticsearch_version" {
  type    = string
  default = "9.3.1"
}

variable "worker_machine_type" {
  type    = string
  default = "e2-standard-8"
}

variable "worker_disk_gb" {
  type    = number
  default = 300
}
