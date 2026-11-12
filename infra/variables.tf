# Inputs. Each has a default, so `terraform plan` works with no extra flags.

variable "region" {
  description = "AWS region for everything (the lookup bucket is in us-east-1)."
  type        = string
  default     = "us-east-1"
}

variable "owner_max_tries" {
  description = "Delivery number on which a lead with no owner is alerted as UNASSIGNED."
  type        = number
  default     = 6
}

variable "log_retention_days" {
  description = "How long CloudWatch keeps Lambda logs."
  type        = number
  default     = 14
}
