import os

site = Site.objects.first()
site.name = 'localhost'
site.domain = 'localhost:8000'
site.save()

user = User.objects.create_superuser(
                    email='oopsdude@gmail.com',
                    password='password')

azure_subscription_id = '6186e102-1a4f-458d-a6bb-b64fd7205cbf'

azure_management_certificate = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDsfzpSRZpppROz
ryoREPcGKq5v49x294QmNPTC3sX3STiGhJ9oVbHm2dZrHMdZrjsZ2wuiMc5Jm34r
qFCI8r6OypzD49ndU7endqUFb50vaGMJCdyArzgcu0fpCXOSynz19C++DUozJhvV
DVrCz9SzqDMiQmiEgJ9MX49f38tVUE1fm/VSFnzxCcD5Ssndao1Brr1BdrIVArAk
hZbAfLkm+LARC5hGNKbRyFq1CmtqLXbvpZzsEWq9fj8pAduOOAIB7DtNvnLmWmT/
KAU6vMyPQeyrrn0EDkh/qCziSwWLAekthXB+kGPjlP7S2mx9vmBhQmayCE27u/+6
Ejm6O8CjAgMBAAECggEAXTBE6uZCUh6aBNOg39ivfd6TncNLvBUMHYIAcEkX+LkB
bQAVUCd0UmLD+rD8XHorD6UgkGjPwHFk5g8MrOn57Iop+4Zs8qlqVLKLk/jHF0cq
vwUDvjFNCwVA8LKot87SLphpt5nFAyKhFPKOMPVz+tbsTzObu5pzKsT82ep1VMft
qCCpWnDcD8fGTCxuEdknQnTA2urSNYTGC/XmQGP45RomvnYd64LckypNaNqA23cf
Vs0Qjlb/cV9WKntfXXjMHKLmSA27gECDGdlXLxmjRQ+qc4jaLTvLDAGJ+eQKTzb8
Lr7eiaf5o/QHjuLRJ4hoTc8Yjy6obpSQcxQNn/hCAQKBgQD/g+PN0h2pAhDSzF7E
lOrKESEv1Prd4/r3UpkDsddRhfTXKeKFB3Mjg4e1J7kgAThq5ZbZu/EJz/SL71uh
73qbhR0boZQkYzbCnPMVhaHZCjDnirQU+aBpTvel+8540NwwYxbP+mPoZ5JWd4/Y
YiypJm8KHiuM+WehXknxUD4KmQKBgQDs8hmvoz3CetSMRcwJvczqkanAqKP8ecOQ
DKaaxFB0i5J7E+uRzS6O0xnwi1X06D5gmaMmhlYrjR0ieTzPGoj2nLMt1srJdOdU
Fcp/U4z4SoJuu5edHY/kMD9gj77O1gzdiC5qgO/cHpxlteokV5aiY9UzrDeP7xaE
+++cmOHGmwKBgQDRmV9FdxbdjNRAF2Wl3IK9P0/57LvdSSaVuyvJ3BjExx4RYkpu
1a2ddEfeUreJiXa+OZeFBKa1ZeE06SRBsjDhYlB+Wg0rzDcfbZ/6B6S8ZZ+4UA9p
JVxxBlYf0m+Mq8fz6VTNRpiuDEf+phVZay83kk+D/Tu8aNqZhL8jNK+wAQKBgQDJ
00I70BFYKaYIQZ+VoJz+JMryNvNPqCwC9DOpWpSpYQWJXqNmUt5Ye8n5kcXK0VPo
lpVYyE531EA/0AMS6ahGX51j6zRaOwCcJ9+PawyFpXnKdnGjO74IAWzKhEZkCgF1
ZX0b7O3ikhRnsndZM140vlKpLAU7zcxhw/MKcVLHBwKBgCb0/QgaU8r1VQmEBgQz
1AeF3la3oyiZO0O0K1KUXat2EFRnCgF05g5jUOYw3Hjx1jy4Q8QKYPQQadtqoiGX
DG2/zB6sFQ8CHfF9xQYtMuJ/Wvrt2UKkDNf0vZ3wHd1iNmDYi2bLO3QEC2e46mbf
TpOXqs5Nhm0nkr0qvvRIM3C4
-----END PRIVATE KEY-----
-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJALUVcuPFcpCwMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
BAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX
aWRnaXRzIFB0eSBMdGQwHhcNMTYwNzI0MDMxODMxWhcNMTYwODIzMDMxODMxWjBF
MQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50
ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB
CgKCAQEA7H86UkWaaaUTs68qERD3Biqub+PcdveEJjT0wt7F90k4hoSfaFWx5tnW
axzHWa47GdsLojHOSZt+K6hQiPK+jsqcw+PZ3VO3p3alBW+dL2hjCQncgK84HLtH
6Qlzksp89fQvvg1KMyYb1Q1aws/Us6gzIkJohICfTF+PX9/LVVBNX5v1UhZ88QnA
+UrJ3WqNQa69QXayFQKwJIWWwHy5JviwEQuYRjSm0chatQprai1276Wc7BFqvX4/
KQHbjjgCAew7Tb5y5lpk/ygFOrzMj0Hsq659BA5If6gs4ksFiwHpLYVwfpBj45T+
0tpsfb5gYUJmsghNu7v/uhI5ujvAowIDAQABo1AwTjAdBgNVHQ4EFgQUDSvSW8lX
9EvxyBKcOOcpGvGSqLgwHwYDVR0jBBgwFoAUDSvSW8lX9EvxyBKcOOcpGvGSqLgw
DAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAM52X8Svew4IGt4HmyhGq
EC0BLJKfOav3lMBvbOwVUf/dtSb3RuBpqOzFzVhJ/lp5NFKjGx+om2VAoYc8ha5p
yYwq2I79knxH8qLYXu0Fi3tEZvp0USnmAkApVmBEGRsspaUIUzi3TLES8WLeyk0O
pf2HUWZYUyYr/8YtY0ypfI0+f6pn0WezRasTZWXs+Gxq6+OYXRoszOgvv5J7eA9y
Pc7GJz0MC8eydGRBDHg0CQMfUgDJxW/g7ATh/EauVaS57TTpbbZUdZBOC6uiv5jg
p2eK1gnjNjQws0uYXA9wsoqVzPL+hcLK/PG5m5IRICorv7FEHYLdYU96OKVtojSq
iA==
-----END CERTIFICATE-----"""

AzureProviderConfiguration.create_account(
                    user=None,
                    subscription_id=azure_subscription_id,
                    management_certificate=azure_management_certificate,
                    location='South Central US')

AzureProviderConfiguration.create_account(
                    user=user,
                    subscription_id=azure_subscription_id,
                    management_certificate=azure_management_certificate,
                    location='South Central US')

AWSProviderConfiguration.create_providers()

aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']

AWSProviderConfiguration.create_regions(
                    user=None,
                    access_key_id=aws_access_key_id,
                    secret_access_key=aws_secret_access_key)

AWSProviderConfiguration.create_regions(
                    user=user,
                    access_key_id=aws_access_key_id,
                    secret_access_key=aws_secret_access_key)
