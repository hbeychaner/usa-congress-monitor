terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.14"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
  }

  # Bucket is supplied at init time: terraform init -backend-config="bucket=<state bucket>"
  backend "gcs" {
    prefix = "congress-tracker"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}
