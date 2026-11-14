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


variable "delay_seconds" {
  description = "How long each new lead waits before the owner lookup (requirement: 10 minutes)."
  type        = number
  default     = 600
}

variable "retry_after_seconds" {
  description = "SQS visibility timeout: a failed message comes back after this long."
  type        = number
  default     = 300
}

variable "max_receive_count" {
  description = "Deliveries before a message moves to the dead-letter queue (must be above owner_max_tries)."
  type        = number
  default     = 10
}

variable "alarm_email" {
  description = "Email that receives DLQ alarms. Set it in infra/terraform.tfvars (git-ignored). Empty = no email subscription."
  type        = string
  default     = ""
}
