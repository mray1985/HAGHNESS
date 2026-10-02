# DigitalOcean hosting cost scenario

Checked October 2, 2026. No resources purchased or deployed. This prices a fictional-document test environment; memory sizes are planning assumptions pending load and scanner measurements.

| Component | Assumed configuration | Monthly published amount |
|---|---|---:|
| Application plus ClamD | Basic Regular Droplet, 8 GiB / 4 vCPU | $48.00 |
| Keycloak identity | Basic Regular Droplet, 4 GiB / 2 vCPU | $24.00 |
| PostgreSQL | Standard Basic Regular single node, 2 GiB / 1 vCPU, minimum storage | $30.45 |
| Private document objects | Spaces Standard base subscription | $5.00 |
| Optional daily VM backups | 30% of the two Droplet prices | $21.60 |
| Priced component subtotal | Including optional daily VM backups | **$129.05** |

Without those VM backups, the component subtotal is $107.45. Arithmetic: 48 + 24 + 30.45 + 5 + (48 + 24) * 0.30 = 129.05. Single-node database and single application/identity hosts do not provide a highly available system. This is not a production capacity recommendation.

## Database plan change

DigitalOcean says new Standard Edition clusters will be limited to 4 GiB and cannot add standby/read-only nodes beginning October 15 for new accounts and November 30 for all accounts. Do not promise a future $60 Standard high-availability cluster. Advanced Edition starts at $130 per primary node, with matching-price standby nodes; an illustrative primary plus standby is $260 before additional storage. Recheck edition, region, availability and checkout prices when the account is ready.

## Expenses still to price

The subtotal excludes independent retained database/object backups, protected historical-key recovery, extra database storage, storage/transfer overages, email, domain, monitoring, support, operations and taxes. Banking/payment services are separate. Spaces includes 250 GiB storage and 1 TiB outbound transfer; storage above that allowance is $0.02/GiB/month. Additional Standard database storage is $0.215/GiB/month.

Native VM backups do not establish our required 35 daily / 12 monthly database-and-document recovery policy. Key custody must remain separately protected; enabling VM images is not proof of independent key recovery. The application backup/export schedule, retention controls and restore exercise still need implementation and hosted verification.

## Official sources

- [Droplet Regular Basic prices](https://www.digitalocean.com/pricing/droplets)
- [Managed database pricing table](https://www.digitalocean.com/pricing/managed-databases)
- [PostgreSQL editions and pricing](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/)
- [Upcoming database plan changes](https://docs.digitalocean.com/release-notes/upcoming/dbaas-plan-changes/)
- [Spaces pricing](https://docs.digitalocean.com/products/spaces/details/pricing/)
- [Backup pricing](https://docs.digitalocean.com/products/backups/details/pricing/)

Next verification: build the Linux deployment, measure memory and API latency with concurrent fictional documents, then verify real MFA, scanning, private object permissions and hosted recovery before inviting clients.
