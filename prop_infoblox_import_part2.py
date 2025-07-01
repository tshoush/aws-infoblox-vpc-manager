'm_host': m_host,
                        'ib_eas': ib_eas,
                        'mapped_eas': mapped_eas,
                        'note': 'Exists as network container - contains subnets'
                    })
                else:
                    # Network exists as regular network
                    logger.debug(f"Network {cidr} (site_id: {site_id}) found in InfoBlox")
                    ib_network = existence_check['object']
                    ib_eas = {k: v.get('value', '') for k, v in ib_network.get('extattrs', {}).items()}
                    
                    # Compare EAs
                    ea_match = self._compare_eas(mapped_eas, ib_eas)
                    
                    if ea_match:
                        logger.debug(f"Network {cidr} (site_id: {site_id}) has matching EAs")
                        results['matches'].append({
                            'property': prop.to_dict(),
                            'cidr': cidr,
                            'ib_network': ib_network,
                            'site_id': site_id,
                            'm_host': m_host,
                            'ib_eas': ib_eas,
                            'mapped_eas': mapped_eas
                        })
                    else:
                        logger.info(f"Network {cidr} (site_id: {site_id}) has EA discrepancies")
                        results['discrepancies'].append({
                            'property': prop.to_dict(),
                            'cidr': cidr,
                            'ib_network': ib_network,
                            'site_id': site_id,
                            'm_host': m_host,
                            'ib_eas': ib_eas,
                            'mapped_eas': mapped_eas
                        })
                        
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing property site_id {site_id} ({cidr}): {error_msg}")
                
                # Try to provide more context about the error
                if "not found" in error_msg.lower() or "404" in error_msg:
                    logger.info(f"Network {cidr} (site_id: {site_id}) appears to not exist in InfoBlox")
                    results['missing'].append({
                        'property': prop.to_dict(),
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'mapped_eas': self.map_properties_to_infoblox_eas(site_id, m_host)
                    })
                else:
                    # Only true errors go here (network issues, parsing errors, etc.)
                    results['errors'].append({
                        'property': prop.to_dict(),
                        'cidr': cidr,
                        'error': error_msg
                    })
        
        return results
    
    def _compare_eas(self, mapped_eas: Dict[str, str], ib_eas: Dict[str, str]) -> bool:
        """Compare mapped property EAs with InfoBlox EAs - returns True only if they match exactly"""
        # Check all keys from both sides
        all_keys = set(mapped_eas.keys()) | set(ib_eas.keys())
        
        for key in all_keys:
            mapped_value = mapped_eas.get(key, None)
            ib_value = ib_eas.get(key, None)
            
            # If key exists in only one side, it's a discrepancy
            if mapped_value is None or ib_value is None:
                return False
            
            # If values don't match, it's a discrepancy
            if str(mapped_value) != str(ib_value):
                return False
        
        return True
    
    def _calculate_network_priority(self, prop: Dict) -> int:
        """Calculate priority for network creation - lower values = higher priority"""
        cidr = prop.get('cidr', '')
        
        # Extract network size from CIDR
        try:
            prefix_len = int(cidr.split('/')[-1])
        except:
            prefix_len = 32  # Default to smallest if can't parse
        
        # Priority is based on network size - larger networks (smaller prefix) get higher priority
        return prefix_len
    
    def ensure_required_eas(self, property_df: pd.DataFrame, dry_run: bool = False) -> Dict:
        """Ensure all required Extended Attributes exist in InfoBlox"""
        # The property file only needs these specific EAs
        required_eas = ['site_id', 'm_host', 'source', 'import_date']
        
        logger.info(f"Ensuring {len(required_eas)} Extended Attributes exist in InfoBlox")
        
        if dry_run:
            # In dry run, just check what would be created
            existing_eas = self.ib_client.get_extensible_attributes()
            existing_names = {ea['name'] for ea in existing_eas}
            missing_eas = [ea for ea in required_eas if ea not in existing_names]
            
            return {
                'missing_eas': missing_eas,
                'existing_count': len(set(required_eas) & existing_names),
                'would_create_count': len(missing_eas)
            }
        else:
            # Actually create missing EAs
            ea_results = self.ib_client.ensure_required_eas_exist(required_eas)
            
            created_count = sum(1 for status in ea_results.values() if status == 'created')
            existing_count = sum(1 for status in ea_results.values() if status == 'exists')
            
            return {
                'ea_results': ea_results,
                'created_count': created_count,
                'existing_count': existing_count
            }
    
    def create_missing_networks(self, missing_networks: List[Dict], network_view: str = "default", 
                               dry_run: bool = False) -> List[Dict]:
        """Create missing networks in InfoBlox"""
        results = []
        
        for item in missing_networks:
            prop = item['property']
            cidr = item['cidr']
            mapped_eas = item['mapped_eas']
            site_id = item['site_id']
            m_host = item['m_host']
            
            try:
                if dry_run:
                    logger.info(f"[DRY RUN] Would create network: {cidr} (site_id: {site_id})")
                    results.append({
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'action': 'would_create',
                        'result': 'success'
                    })
                else:
                    # Create the network
                    comment = f"Property Network: {m_host} (Site ID: {site_id})"
                    result = self.ib_client.create_network(
                        cidr=cidr,
                        network_view=network_view,
                        comment=comment,
                        extattrs=mapped_eas
                    )
                    
                    logger.info(f"Created network: {cidr} (site_id: {site_id})")
                    results.append({
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'action': 'created',
                        'result': 'success',
                        'ref': result
                    })
                    
            except Exception as e:
                error_msg = str(e)
                error_lower = error_msg.lower()
                
                # Check if network already exists (not really an error)
                if 'already exists' in error_lower or 'duplicate' in error_lower:
                    logger.info(f"Network {cidr} already exists - checking if EAs need updating")
                    
                    # Try to get the existing network and update its EAs
                    try:
                        existing_network = self.ib_client.get_network_by_cidr(cidr, network_view)
                        if existing_network:
                            # Update the EAs on the existing network
                            network_ref = existing_network['_ref']
                            self.ib_client.update_network_extattrs(network_ref, mapped_eas)
                            logger.info(f"Updated EAs for existing network: {cidr}")
                            
                            results.append({
                                'cidr': cidr,
                                'site_id': site_id,
                                'm_host': m_host,
                                'action': 'already_existed_updated_eas',
                                'result': 'success'
                            })
                        else:
                            results.append({
                                'cidr': cidr,
                                'site_id': site_id,
                                'm_host': m_host,
                                'action': 'already_existed',
                                'result': 'success'
                            })
                    except Exception as update_error:
                        logger.warning(f"Could not update EAs for existing network {cidr}: {update_error}")
                        results.append({
                            'cidr': cidr,
                            'site_id': site_id,
                            'm_host': m_host,
                            'action': 'already_existed_ea_update_failed',
                            'error': str(update_error),
                            'property': prop
                        })
                else:
                    # This is a real error
                    logger.error(f"Failed to create network {cidr}: {error_msg}")
                    
                    # Categorize the error
                    category = 'unknown'
                    if 'overlap' in error_lower or 'parent' in error_lower:
                        category = 'overlap'
                    elif 'permission' in error_lower or 'auth' in error_lower:
                        category = 'permission'
                    elif 'invalid' in error_lower:
                        category = 'invalid'
                    elif 'network view' in error_lower:
                        category = 'network_view_error'
                    elif 'not found' in error_lower:
                        category = 'not_found'
                    elif 'extensible' in error_lower or 'attribute' in error_lower:
                        category = 'ea_error'
                    
                    # Log detailed debugging info
                    logger.debug(f"Network creation failed - Category: {category}")
                    logger.debug(f"Property Details: Site ID={site_id}, Host={m_host}, CIDR={cidr}")
                    logger.debug(f"Extended Attributes: {mapped_eas}")
                    
                    results.append({
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'action': 'error',
                        'error': error_msg,
                        'category': category,
                        'property': prop
                    })
        
        # Generate status CSV files
        if not dry_run:
            self._generate_creation_status_csv(results)
        
        return results
    
    def _generate_creation_status_csv(self, results: List[Dict]):
        """Generate CSV file with network creation status"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"property_network_creation_status_{timestamp}.csv"
        
        data = []
        for result in results:
            data.append({
                'CIDR': result['cidr'],
                'Site_ID': result['site_id'],
                'Host': result['m_host'],
                'Action': result['action'],
                'Error': result.get('error', ''),
                'Category': result.get('category', '')
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Generated network creation status report: {filename}")
    
    def fix_ea_discrepancies(self, discrepancies: List[Dict], dry_run: bool = False) -> Dict:
        """Fix EA discrepancies by updating networks with correct EAs from properties file"""
        results = {
            'updated_count': 0,
            'would_update_count': 0,
            'failed_count': 0,
            'details': []
        }
        
        for item in discrepancies:
            cidr = item['cidr']
            ib_network = item['ib_network']
            mapped_eas = item['mapped_eas']
            site_id = item['site_id']
            m_host = item['m_host']
            
            try:
                if dry_run:
                    logger.info(f"[DRY RUN] Would update EAs for network: {cidr} (site_id: {site_id})")
                    results['would_update_count'] += 1
                    results['details'].append({
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'action': 'would_update',
                        'current_eas': item['ib_eas'],
                        'new_eas': mapped_eas
                    })
                else:
                    # Update the network's EAs
                    network_ref = ib_network['_ref']
                    self.ib_client.update_network_extattrs(network_ref, mapped_eas)
                    
                    logger.info(f"Updated EAs for network: {cidr} (site_id: {site_id})")
                    results['updated_count'] += 1
                    results['details'].append({
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'action': 'updated',
                        'old_eas': item['ib_eas'],
                        'new_eas': mapped_eas
                    })
                    
            except Exception as e:
                logger.error(f"Failed to update EAs for network {cidr}: {e}")
                results['failed_count'] += 1
                results['details'].append({
                    'cidr': cidr,
                    'site_id': site_id,
                    'm_host': m_host,
                    'action': 'error',
                    'error': str(e)
                })
        
        return results


def generate_ea_discrepancies_report(discrepancies: List[Dict]):
    """Generate detailed report of EA discrepancies"""
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(reports_dir, f"property_ea_discrepancies_{timestamp}.md")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Property Network Extended Attributes Discrepancies Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total networks with EA discrepancies: {len(discrepancies)}\n\n")
        
        f.write("## Detailed Discrepancies\n\n")
        
        for item in discrepancies:
            site_id = item['site_id']
            m_host = item['m_host']
            cidr = item['cidr']
            
            f.write(f"### {cidr} - Site ID: {site_id}\n\n")
            f.write(f"- **Host**: {m_host}\n\n")
            
            f.write("#### Current InfoBlox EAs:\n```\n")
            for k, v in sorted(item['ib_eas'].items()):
                f.write(f"{k}: {v}\n")
            f.write("```\n\n")
            
            f.write("#### Expected EAs from Properties File:\n```\n")
            for k, v in sorted(item['mapped_eas'].items()):
                f.write(f"{k}: {v}\n")
            f.write("```\n\n")
            
            f.write("#### Differences:\n")
            all_keys = set(item['ib_eas'].keys()) | set(item['mapped_eas'].keys())
            for key in sorted(all_keys):
                ib_val = item['ib_eas'].get(key, '(missing)')
                prop_val = item['mapped_eas'].get(key, '(missing)')
                if ib_val != prop_val:
                    f.write(f"- **{key}**: `{ib_val}` → `{prop_val}`\n")
            
            f.write("\n---\n\n")
    
    logger.info(f"Generated EA discrepancies report: {filename}")


def generate_network_status_report(comparison_results: Dict, dry_run: bool = False):
    """Generate comprehensive network status report"""
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(reports_dir, f"property_network_status_report_{timestamp}.md")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Property File to InfoBlox Network Status Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- **Total Networks Analyzed**: {sum(len(v) for v in comparison_results.values())}\n")
        f.write(f"- **Fully Synchronized Networks**: {len(comparison_results['matches'])}\n")
        f.write(f"- **Missing from InfoBlox**: {len(comparison_results['missing'])}\n")
        f.write(f"- **Networks with Outdated EAs**: {len(comparison_results['discrepancies'])}\n")
        f.write(f"- **Network Containers**: {len(comparison_results['containers'])}\n")
        f.write(f"- **Processing Errors**: {len(comparison_results['errors'])}\n\n")
        
        # Missing Networks
        if comparison_results['missing']:
            f.write("## Missing Networks\n\n")
            f.write("These networks exist in the properties file but not in InfoBlox:\n\n")
            f.write("| CIDR | Site ID | Host |\n")
            f.write("|------|---------|------|\n")
            
            for item in comparison_results['missing']:
                f.write(f"| {item['cidr']} | {item['site_id']} | {item['m_host']} |\n")
            f.write("\n")
        
        # Network Containers
        if comparison_results['containers']:
            f.write("## Network Containers\n\n")
            f.write("These networks exist as network containers in InfoBlox:\n\n")
            f.write("| CIDR | Site ID | Host | Note |\n")
            f.write("|------|---------|------|------|\n")
            
            for item in comparison_results['containers']:
                f.write(f"| {item['cidr']} | {item['site_id']} | {item['m_host']} | {item['note']} |\n")
            f.write("\n")
        
        # Processing Errors
        if comparison_results['errors']:
            f.write("## Processing Errors\n\n")
            f.write("Errors encountered during processing:\n\n")
            
            for item in comparison_results['errors']:
                prop = item['property']
                f.write(f"### {item['cidr']} - Site ID: {prop.get('site_id', 'Unknown')}\n")
                f.write(f"- **Error**: {item['error']}\n")
                f.write(f"- **Host**: {prop.get('m_host', 'Unknown')}\n\n")
    
    logger.info(f"Generated network status report: {filename}")


def main():
    """Main function with all enhanced features"""
    args = parse_arguments()
    
    try:
        config_override = None
        
        # Check if interactive mode is requested
        if args.interactive:
            # Show and optionally edit configuration
            config_override = show_and_edit_config()
        else:
            # Quiet mode - just load from config.env
            logger.info("Running in quiet mode. Use -i for interactive configuration.")
        
        # Get configuration (no prompting in quiet mode)
        grid_master, network_view, username, password, csv_file, container_prefixes, container_mode = get_config(
            config_override=config_override
        )
        
        # Override network view if specified on command line
        if args.network_view:
            network_view = args.network_view
            print(f"Using network view from command line: {network_view}")
            
        # Override CSV file if specified on command line
        if args.csv_file and args.csv_file != 'modified_properties_file.csv':
            csv_file = args.csv_file
            print(f"Using CSV file from command line: {csv_file}")
        
        # Show container configuration
        if container_prefixes:
            print(f"📦 Container prefixes configured: /{', /'.join(map(str, container_prefixes))}")
            print(f"🔧 Container mode: {container_mode}")
        else:
            print("📦 Container detection: Auto-detect from InfoBlox")
        
        logger.info(f"Loading property data from {csv_file}...")
        
        # Initialize InfoBlox client
        print(f"\n🔗 Connecting to InfoBlox Grid Master: {grid_master}")
        ib_client = InfoBloxClient(grid_master, username, password)
        
        # Initialize Property Manager
        prop_manager = PropertyManager(ib_client)
        
        # Load and parse property data
        try:
            property_df = prop_manager.load_property_data(csv_file)
            property_df = prop_manager.parse_prefixes(property_df)
        except Exception as e:
            logger.error(f"Failed to load property data: {e}")
            return 1
        
        print(f"\n📊 ANALYSIS SUMMARY:")
        print(f"   📁 CSV file: {csv_file}")
        print(f"   🔢 Total networks loaded: {len(property_df)}")
        print(f"   🌐 Network view: {network_view}")
        
        # Compare with InfoBlox
        logger.info("Comparing property networks with InfoBlox...")
        comparison_results = prop_manager.compare_properties_with_infoblox(property_df, network_view)
        
        # Display results
        print(f"\n🔍 COMPARISON RESULTS:")
        print(f"   ✅ Fully synchronized (network + EAs): {len(comparison_results['matches'])}")
        print(f"   🔴 Missing from InfoBlox: {len(comparison_results['missing'])}")
        print(f"   🟡 Networks with outdated EAs: {len(comparison_results['discrepancies'])}")
        print(f"   📦 Network containers: {len(comparison_results['containers'])}")
        print(f"   ❌ Processing errors: {len(comparison_results['errors'])}")
        
        # Show update requirements summary
        if comparison_results['discrepancies']:
            print(f"\n🔧 UPDATE REQUIREMENTS:")
            print(f"   🏷️ Networks requiring EA updates: {len(comparison_results['discrepancies'])}")
            
            # Show sample of networks that need updates
            sample_discrepancies = comparison_results['discrepancies'][:3]
            for item in sample_discrepancies:
                site_id = item['site_id']
                m_host = item['m_host']
                cidr = item['cidr']
                print(f"   📄 {cidr} (Site: {site_id}, Host: {m_host}) - EAs need updating")
            
            if len(comparison_results['discrepancies']) > 3:
                print(f"   ... and {len(comparison_results['discrepancies']) - 3} more networks")
        
        # Show network containers summary
        if comparison_results.get('containers'):
            print(f"\n📦 NETWORK CONTAINERS FOUND:")
            print(f"   🔢 Networks existing as containers: {len(comparison_results['containers'])}")
            print(f"   ℹ️ These exist as network containers (parent networks) in InfoBlox")
            print(f"   💡 Container networks typically contain smaller subnet networks")
            for container in comparison_results['containers'][:3]:
                print(f"   📦 {container['cidr']} - Site: {container['site_id']}")
            if len(comparison_results['containers']) > 3:
                print(f"   ... and {len(comparison_results['containers']) - 3} more")
        
        # Analyze Extended Attributes (regardless of missing networks)
        if args.create_missing:
            print(f"\n🔍 EXTENDED ATTRIBUTES ANALYSIS:")
            ea_analysis = prop_manager.ensure_required_eas(property_df, dry_run=args.dry_run)
            
            # Generate EA summary report
            reports_dir = "reports"
            os.makedirs(reports_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ea_report_filename = os.path.join(reports_dir, f"property_extended_attributes_summary_{timestamp}.txt")
            
            eas_to_report = []
            report_ea_title = ""

            if args.dry_run:
                print(f"   🏷️ Extended Attributes analysis: {len(ea_analysis['missing_eas'])} missing")
                eas_to_report = ea_analysis.get('missing_eas', [])
                report_ea_title = "Missing Extended Attributes (would be created):"
            else:
                print(f"   🏷️ Extended Attributes: {ea_analysis['created_count']} created, {ea_analysis['existing_count']} existed")
                created_eas = [name for name, status in ea_analysis.get('ea_results', {}).items() if status == 'created']
                eas_to_report = created_eas
                report_ea_title = "Extended Attributes Created:"

            if eas_to_report:
                with open(ea_report_filename, 'w', encoding='utf-8') as f:
                    f.write(f"{report_ea_title}\n")
                    f.write("=" * len(report_ea_title) + "\n")
                    for ea_name in eas_to_report:
                        f.write(f"{ea_name}\n")
                logger.info(f"Generated Extended Attributes summary: {ea_report_filename}")
                print(f"   📄 Extended Attributes summary file: {ea_report_filename}")
            else:
                logger.info("No new or missing Extended Attributes to report.")

        # Handle create-missing flag for networks
        if args.create_missing and comparison_results['missing']:
            print(f"\n🚀 CREATING MISSING NETWORKS:")
            
            # Sort missing networks by priority (larger networks first)
            missing_with_priority = []
            for item in comparison_results['missing']:
                prop = item['property']
                priority = prop_manager._calculate_network_priority(prop)
                missing_with_priority.append((priority, item))
            
            # Sort by priority
            missing_with_priority.sort(key=lambda x: x[0])
            sorted_missing = [item for priority, item in missing_with_priority]
            
            print(f"   📋 Creating {len(sorted_missing)} networks in priority order...")
            print(f"   🔢 Priority order: larger networks (/16, /17) before smaller (/24, /25)")
            
            # Create networks
            operation_results = prop_manager.create_missing_networks(
                sorted_missing, 
                network_view=network_view, 
                dry_run=args.dry_run
            )
            
            # Show results
            created_count = sum(1 for r in operation_results if r.get('action') == 'created')
            would_create_count = sum(1 for r in operation_results if r.get('action') == 'would_create')
            error_count = sum(1 for r in operation_results if r.get('action') == 'error')
            
            if args.dry_run:
                print(f"   ✅ Would create: {would_create_count}")
                print(f"   ❌ Would fail: {error_count}")
            else:
                print(f"   ✅ Successfully created: {created_count}")
                print(f"   ❌ Failed to create: {error_count}")
                if error_count > 0:
                    print(f"   📄 Check creation status CSV for failed creations")
        
        # Handle EA Discrepancies
        if args.create_missing and comparison_results['discrepancies']:
            print(f"\n🔧 FIXING EA DISCREPANCIES:")
            discrepancy_results = prop_manager.fix_ea_discrepancies(
                comparison_results['discrepancies'], 
                dry_run=args.dry_run
            )
            
            if args.dry_run:
                print(f"   🔧 Would update {discrepancy_results['would_update_count']} networks with correct EAs")
            else:
                print(f"   ✅ Updated {discrepancy_results['updated_count']} networks")
                print(f"   ❌ Failed to update {discrepancy_results['failed_count']} networks")

        # Generate EA Discrepancies Report
        if comparison_results['discrepancies']:
            generate_ea_discrepancies_report(comparison_results['discrepancies'])
        
        # Generate Comprehensive Network Status Report
        generate_network_status_report(comparison_results, args.dry_run)

        print(f"\n✅ OPERATION COMPLETED")
        print(f"   📝 Check logs: prop_infoblox_import.log")
        print(f"   📊 For detailed reports, check the reports/ directory")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
