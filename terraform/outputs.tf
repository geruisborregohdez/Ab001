output "public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_eip.app.public_ip
}

output "app_url" {
  description = "Application URL"
  value       = "http://${aws_eip.app.public_ip}"
}

output "mcp_sse_url" {
  description = "MCP SSE endpoint for external clients"
  value       = "http://${aws_eip.app.public_ip}/mcp/sse"
}

output "api_url" {
  description = "REST API base URL"
  value       = "http://${aws_eip.app.public_ip}/api"
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ec2-user@${aws_eip.app.public_ip}"
}
