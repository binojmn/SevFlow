data "http" "my_ip" {
  url = var.my_ip_lookup_url
}

data "aws_ami" "ubuntu" {
  most_recent = var.bastion_ami_most_recent

  filter {
    name   = "name"
    values = [var.bastion_ami_name_filter]
  }

  filter {
    name   = "virtualization-type"
    values = [var.bastion_ami_virtualization_type]
  }

  owners = var.bastion_ami_owners
}
