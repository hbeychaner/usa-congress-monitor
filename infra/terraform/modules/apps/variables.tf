variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "domain" { type = string }
variable "iap_members" { type = list(string) }
variable "network" { type = string }
variable "subnetwork" { type = string }
variable "backend_image" { type = string }
variable "frontend_image" { type = string }
variable "api_service_account" { type = string }
variable "api_min_instances" { type = number }
variable "es_url" { type = string }
variable "redis_url" { type = string }

variable "secret_ids" {
  type        = map(string)
  description = "Secret Manager secret ids keyed by purpose: elastic_api_key, rabbitmq_url, congress_api_key."
}
