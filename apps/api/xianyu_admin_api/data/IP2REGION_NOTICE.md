# Offline IP data notices

`ip2region_v4.xdb` is sourced from the `lionsoul2014/ip2region` project and is
used for offline proxy egress IP location display.

- Project: https://github.com/lionsoul2014/ip2region
- License: Apache License 2.0
- Database format: `Country|Province|City|ISP|iso-alpha2-code`

The bundled file is redistributed under the upstream Apache License 2.0 terms.

`geoip.db` is an IPinfo free country database in MMDB format and is used to
display country and continent metadata for IPv6 egress addresses.

- Provider: https://ipinfo.io/
- Product information: https://ipinfo.io/products/free-ip-database
- License: Creative Commons Attribution-ShareAlike 4.0 International
- Attribution: IP address data powered by IPinfo

The MMDB format is read with the `maxminddb` Python package.
