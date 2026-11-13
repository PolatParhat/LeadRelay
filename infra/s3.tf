# The one LeadRelay bucket: source/ (raw events), target/ (enriched), alerts_sent/ (markers).

resource "aws_s3_bucket" "leads" {
  bucket = local.bucket_name

  # Lets `terraform destroy` delete the bucket even when it still holds files.
  # Fine for this project (Step 7 tears everything down); never do this for data you must keep.
  force_destroy = true
}

# Nobody on the internet can read it: block every form of public access.
resource "aws_s3_bucket_public_access_block" "leads" {
  bucket                  = aws_s3_bucket.leads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# The bucket owner (our account) owns every object; ACLs (old-style permissions) are switched off.
resource "aws_s3_bucket_ownership_controls" "leads" {
  bucket = aws_s3_bucket.leads.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Encrypt every file at rest with S3-managed keys (free).
resource "aws_s3_bucket_server_side_encryption_configuration" "leads" {
  bucket = aws_s3_bucket.leads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Refuse any request that does not use HTTPS (data is never sent unencrypted).
resource "aws_s3_bucket_policy" "leads" {
  bucket = aws_s3_bucket.leads.id
  policy = data.aws_iam_policy_document.leads_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.leads]
}

data "aws_iam_policy_document" "leads_bucket" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.leads.arn, "${aws_s3_bucket.leads.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# Versioning stays off on purpose: files are overwritten by design (one file per lead) and
# markers are deleted on Slack failure; old versions would only pile up.
