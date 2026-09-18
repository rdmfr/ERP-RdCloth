# NexaBiz ERP Support Policy

## Included

- Installation guidance for the documented local and Docker setup.
- Bug fixes for reproducible defects in the purchased version.
- Documentation clarification.
- Security notices for supported versions.

## Not included

- Hosting, MongoDB administration, domain, DNS, TLS, email, or backups.
- Custom integrations, tax advice, accounting advice, or data recovery caused by
  missing buyer backups.
- Custom design or feature development unless separately agreed.

## Buyer responsibilities

Use unique production secrets, enable HTTPS, restrict CORS, disable demo mode, update
dependencies, and test backups and restores regularly. Keep a copy of the purchase
receipt and version number when requesting support. Never send passwords, JWT secrets,
database URLs, or customer data in a support request.

## Version policy

Support applies to the purchased release and the latest maintenance release of the
same major version. Updates may require a backup and migration review before deployment.
