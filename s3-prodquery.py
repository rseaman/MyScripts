#!/usr/bin/env python3

"""
This script is vibe-coded, and can only tell lies. It could *probably* be improved and made more useful.
Consider the various following readouts to be interfaces to be *implemented*.
It was a quick hack to solve a problem I needed a complex answer for fast.
"""

import boto3
import re
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, BotoCoreError
import json

class S3ProductionAnalyzer:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.cloudwatch_client = boto3.client('cloudwatch')
    
    def analyze_production_indicators(self, bucket_name):
        """Analyze a bucket for production indicators and return a score."""
        prod_score = 0
        indicators = []
        
        print(f"🔍 Production Indicators for: {bucket_name}")
        
        # 1. Check naming patterns
        prod_score, indicators = self._check_naming_patterns(bucket_name, prod_score, indicators)
        
        # 2. Check tags
        prod_score, indicators = self._check_tags(bucket_name, prod_score, indicators)
        
        # 3. Check recent activity (last 7 days)
        prod_score, indicators = self._check_recent_activity(bucket_name, prod_score, indicators)
        
        # 4. Check data transfer (indicates real usage)
        prod_score, indicators = self._check_data_transfer(bucket_name, prod_score, indicators)
        
        # 5. Check object count and size
        prod_score, indicators = self._check_contents(bucket_name, prod_score, indicators)
        
        # 6. Check for recent modifications
        prod_score, indicators = self._check_recent_modifications(bucket_name, prod_score, indicators)
        
        # Production likelihood assessment
        self._print_assessment(prod_score, indicators)
        
        return prod_score
    
    def _check_naming_patterns(self, bucket_name, prod_score, indicators):
        """Check bucket name for production/non-production patterns."""
        if re.search(r'(prod|production)', bucket_name, re.IGNORECASE):
            prod_score += 3
            indicators.append("✅ Contains 'prod' in name (+3)")
        elif re.search(r'(dev|development|test|staging|integration|sandbox)', bucket_name, re.IGNORECASE):
            prod_score -= 2
            indicators.append("❌ Contains non-prod keywords (-2)")
        
        return prod_score, indicators
    
    def _check_tags(self, bucket_name, prod_score, indicators):
        """Check bucket tags for environment indicators."""
        print("  📋 Checking tags...")
        
        try:
            response = self.s3_client.get_bucket_tagging(Bucket=bucket_name)
            tags = {tag['Key']: tag['Value'] for tag in response['TagSet']}
            
            # Look for environment-related tags
            env_keys = ['Environment', 'environment', 'Env', 'env']
            env_value = None
            
            for key in env_keys:
                if key in tags:
                    env_value = tags[key]
                    break
            
            if env_value:
                if re.match(r'^(prod|production|Production|PROD)$', env_value):
                    prod_score += 5
                    indicators.append(f"✅ Environment tag = {env_value} (+5)")
                elif re.match(r'^(dev|development|test|staging|integration|sandbox)$', env_value):
                    prod_score -= 3
                    indicators.append(f"❌ Environment tag = {env_value} (-3)")
            
            tag_display = ', '.join([f"{k}={v}" for k, v in tags.items()])
            print(f"    Tags: {tag_display}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchTagSet':
                print("    Tags: None")
                indicators.append("⚠️  No tags (consider this suspicious)")
            else:
                print(f"    Tags: Error accessing tags - {e}")
        
        return prod_score, indicators
    
    def _check_recent_activity(self, bucket_name, prod_score, indicators):
        """Check CloudWatch metrics for recent request activity."""
        print("  📊 Checking recent activity...")
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=7)
            
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='AllRequests',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=604800,  # 1 week
                Statistics=['Sum']
            )
            
            if response['Datapoints']:
                recent_requests = response['Datapoints'][0]['Sum']
                
                if recent_requests > 1000:
                    prod_score += 3
                    indicators.append(f"✅ High activity: {recent_requests:.0f} requests/week (+3)")
                elif recent_requests > 100:
                    prod_score += 1
                    indicators.append(f"🔶 Moderate activity: {recent_requests:.0f} requests/week (+1)")
                else:
                    indicators.append(f"🔶 Low activity: {recent_requests:.0f} requests/week")
                
                print(f"    Recent requests (7d): {recent_requests:.0f}")
            else:
                print("    Recent requests (7d): No data or no activity")
                indicators.append("❓ No recent activity data")
                
        except Exception as e:
            print(f"    Recent requests (7d): Error - {e}")
            indicators.append("❓ Error checking activity")
        
        return prod_score, indicators
    
    def _check_data_transfer(self, bucket_name, prod_score, indicators):
        """Check data transfer metrics."""
        print("  📈 Checking data transfer...")
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)
            
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BytesDownloaded',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=2592000,  # 30 days
                Statistics=['Sum']
            )
            
            if response['Datapoints']:
                bytes_downloaded = response['Datapoints'][0]['Sum']
                gb_downloaded = bytes_downloaded / (1024 ** 3)  # Convert to GB
                
                if gb_downloaded > 10:
                    prod_score += 2
                    indicators.append(f"✅ Significant data transfer: {gb_downloaded:.2f}GB downloaded (+2)")
                
                print(f"    Data downloaded (30d): {gb_downloaded:.2f}GB")
            else:
                print("    Data downloaded (30d): No data")
                
        except Exception as e:
            print(f"    Data downloaded (30d): Error - {e}")
        
        return prod_score, indicators
    
    def _check_contents(self, bucket_name, prod_score, indicators):
        """Check bucket contents for object count."""
        print("  📦 Checking contents...")
        
        try:
            # Get object count using list_objects_v2 with pagination
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name)
            
            object_count = 0
            total_size = 0
            
            for page in page_iterator:
                if 'Contents' in page:
                    object_count += len(page['Contents'])
                    total_size += sum(obj['Size'] for obj in page['Contents'])
            
            if object_count > 1000:
                prod_score += 1
                indicators.append(f"✅ Large object count: {object_count:,} objects (+1)")
            
            # Convert size to human readable
            if total_size > 0:
                size_gb = total_size / (1024 ** 3)
                print(f"    Total Objects: {object_count:,}")
                print(f"    Total Size: {size_gb:.2f} GB")
            else:
                print(f"    Total Objects: {object_count:,}")
                print("    Total Size: 0 Bytes")
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDenied':
                print("    Contents: Access denied")
            else:
                print(f"    Contents: Error - {e}")
        except Exception as e:
            print(f"    Contents: Error - {e}")
        
        return prod_score, indicators
    
    def _check_recent_modifications(self, bucket_name, prod_score, indicators):
        """Check for recent object modifications."""
        print("  🕒 Checking recent modifications...")
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                MaxKeys=100
            )
            
            if 'Contents' in response and response['Contents']:
                # Sort by LastModified and get the most recent
                sorted_objects = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
                most_recent = sorted_objects[0]['LastModified']
                
                # Check if modified in the last week
                week_ago = datetime.now(most_recent.tzinfo) - timedelta(days=7)
                
                if most_recent > week_ago:
                    prod_score += 1
                    indicators.append(f"✅ Recently modified: {most_recent.strftime('%Y-%m-%d %H:%M:%S')} (+1)")
                
                print(f"    Last modification: {most_recent.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("    Last modification: No objects")
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDenied':
                print("    Last modification: Access denied")
            else:
                print(f"    Last modification: Error - {e}")
        except Exception as e:
            print(f"    Last modification: Error - {e}")
        
        return prod_score, indicators
    
    def _print_assessment(self, prod_score, indicators):
        """Print the production assessment."""
        print()
        print("  🎯 PRODUCTION ASSESSMENT:")
        for indicator in indicators:
            print(f"    {indicator}")
        
        print(f"  📊 Production Score: {prod_score}")
        
        if prod_score >= 5:
            print("  🔴 LIKELY PRODUCTION - High confidence")
        elif prod_score >= 2:
            print("  🟡 POSSIBLY PRODUCTION - Medium confidence")
        elif prod_score >= 0:
            print("  🟢 LIKELY NON-PRODUCTION - Low risk")
        else:
            print("  ⚪ CLEARLY NON-PRODUCTION - Safe to investigate")
        
        print("  " + "=" * 60)
    
    def analyze_all_buckets(self):
        """Analyze all S3 buckets in the account."""
        print("S3 Bucket Production Analysis")
        print("=" * 29)
        
        try:
            response = self.s3_client.list_buckets()
            buckets = response['Buckets']
            
            production_buckets = []
            maybe_production = []
            
            for bucket in buckets:
                bucket_name = bucket['Name']
                print()
                score = self.analyze_production_indicators(bucket_name)
                
                if score >= 5:
                    production_buckets.append((bucket_name, score))
                elif score >= 2:
                    maybe_production.append((bucket_name, score))
                
                print()
            
            # Print summary
            print()
            print("🎯 SUMMARY RECOMMENDATIONS:")
            print("• RED (5+ points): Treat as production, investigate carefully")
            print("• YELLOW (2-4 points): Verify with team before making changes")
            print("• GREEN (0-1 points): Likely safe for cleanup/investigation")
            print("• WHITE (negative): Development/test buckets")
            
            if production_buckets:
                print()
                print("🔴 HIGH CONFIDENCE PRODUCTION BUCKETS:")
                for bucket_name, score in sorted(production_buckets, key=lambda x: x[1], reverse=True):
                    print(f"  • {bucket_name} (score: {score})")
            
            if maybe_production:
                print()
                print("🟡 POSSIBLE PRODUCTION BUCKETS:")
                for bucket_name, score in sorted(maybe_production, key=lambda x: x[1], reverse=True):
                    print(f"  • {bucket_name} (score: {score})")
                    
        except Exception as e:
            print(f"Error listing buckets: {e}")

def main():
    """Main execution function."""
    analyzer = S3ProductionAnalyzer()
    analyzer.analyze_all_buckets()

if __name__ == "__main__":
    main()