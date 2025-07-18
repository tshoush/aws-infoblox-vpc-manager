# AWS VPC to InfoBlox Comparison Report
*Generated on 2025-06-03 17:47:51*

## Overview
This report compares AWS VPC data with InfoBlox networks, focusing on subnet CIDR blocks and tag mapping to Extended Attributes.

## Summary
- **Total VPCs Analyzed**: 3
- **Matching Networks**: 1
- **Missing Networks**: 1
- **Networks with Discrepancies**: 1
- **Processing Errors**: 0

## Matching Networks
Networks that exist in both AWS and InfoBlox with consistent tags/EAs.

| VPC Name | CIDR | Account ID | Region | Status |
|----------|------|------------|---------|--------|
| existing-vpc | 10.0.0.0/16 | 123456789 | us-east-1 | ✅ Match |

## Missing Networks in InfoBlox
AWS VPCs that don't exist in InfoBlox and need to be created.

| VPC Name | CIDR | Account ID | Region | Recommended Action |
|----------|------|------------|---------|-------------------|
| new-vpc | 10.1.0.0/16 | 123456789 | us-west-2 | 🔴 Create Network |

## Networks with Tag/EA Discrepancies
Networks that exist in both systems but have different tags/Extended Attributes.

| VPC Name | CIDR | Account ID | Region | Recommended Action |
|----------|------|------------|---------|-------------------|
| mismatched-vpc | 10.2.0.0/16 | 123456789 | us-east-1 | 🟡 Update EAs |

## Recommendations

1. **Create Missing Networks**: Use the `create_missing_networks()` function to add missing VPC subnets to InfoBlox.
2. **Update Discrepant Networks**: Use the `update_discrepant_networks()` function to sync tag differences.

---
*Report generated by AWS-InfoBlox VPC Manager*