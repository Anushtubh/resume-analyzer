# AWS deployment path (EC2 + S3)

This guide describes deployment; it does not create AWS resources. The app
continues to run locally with SQLite file storage unless explicitly configured
for S3.

## Responsibilities

- **EC2:** runs the FastAPI application and browser UI.
- **S3:** stores original uploaded PDF/DOCX files when
  `RESUME_STORAGE_BACKEND=s3` is enabled.
- **SQLite on the EC2 EBS volume:** retains recruiter accounts, candidate
  profiles, embeddings, and S3 object references. In S3 mode, SQLite stores an
  empty file placeholder rather than a second copy of the resume.
- **FAISS on the EC2 EBS volume:** local per-user search index, recoverable from
  the vectors in SQLite.

This remains a **single-EC2 prototype**. SQLite and FAISS are not shared stores;
do not run multiple application instances against them. Use an encrypted,
durable EBS volume and tested snapshots. Do not put SQLite or FAISS files in S3.

## S3 configuration

1. Create a private S3 bucket in the same AWS region as the EC2 instance. Keep
   Block Public Access enabled, enable bucket default encryption, and consider
   versioning and lifecycle retention based on your college/demo data policy.
2. Attach an EC2 instance role (instance profile) limited to the chosen bucket
   and `resumes/*` prefix. The app needs `s3:PutObject` and `s3:DeleteObject`
   on that prefix. Add `s3:GetObject` only if a future feature needs downloads.
   Bucket listing is not required by the current code.
3. Set the following in the app environment:

   ```ini
   RESUME_STORAGE_BACKEND=s3
   S3_BUCKET=your-private-bucket-name
   S3_RESUME_PREFIX=resumes
   AWS_REGION=ap-south-1
   ```

   `boto3` uses the standard AWS credential provider chain. On EC2, prefer the
   attached instance role; do not paste access keys into `.env`, source code, or
   Git. Uploads use server-side AES-256 encryption and keys scoped by user ID
   and candidate ID. The UI's existing batch limits still apply.

Switching the setting does not migrate previously stored SQLite resume blobs.
Existing records continue to work; new uploads go to S3. Plan and test any
historical-data migration separately.

## EC2 deployment outline

1. Choose a supported Ubuntu LTS AMI, region, disk size, and instance class
   appropriate for both the BERT-NER checkpoint and SBERT inference. This
   project has no need to train the model on EC2; package or transfer the
   already-trained checkpoint through an approved private artifact channel.
2. Place the instance in a VPC/subnet and attach the S3 instance role. Restrict
   SSH to a trusted administrator IP or use AWS Systems Manager Session Manager.
   Do not expose port 8000 to the public internet.
3. Clone the project to the EBS-backed application directory; create a Python
   virtual environment and install `requirements.txt`. Copy the model checkpoint
   and configure the environment values above in a root-readable service env
   file. Keep the SQLite database, FAISS index, and session secret on the EBS
   volume, outside disposable deployment directories.
4. Run Uvicorn bound to `127.0.0.1:8000` under a dedicated systemd service. Put
   Nginx or an AWS load balancer with HTTPS in front of it. Permit inbound
   HTTPS only from the intended audience. Use a valid TLS certificate so the
   session cookie is marked secure.
5. Configure log rotation, EBS snapshots, S3 lifecycle/retention, monitoring,
   and a tested restore procedure before using real resumes.
6. Verify sign-in, upload, S3 object creation, candidate processing, JD search,
   ranking, server restart, and EBS restore using synthetic resumes first.

The project intentionally does not select an AWS region, instance type, VPC,
public access policy, bucket name, or retention period for you. Those choices
affect cost, security, and availability and should be made before provisioning.

## Local mode

Leave `RESUME_STORAGE_BACKEND=sqlite` (or unset it) to keep the existing local
behavior. No AWS account or credentials are needed in that mode.
