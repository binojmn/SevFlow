# Generate a key and registers it in AWS.

resource "tls_private_key" "bastion_key" {
  algorithm = var.bastion_key_algorithm
  rsa_bits  = var.bastion_key_rsa_bits
}

resource "aws_key_pair" "bastion_keypair" {
  key_name   = var.bastion_key_name
  public_key = tls_private_key.bastion_key.public_key_openssh
}


# Save the private key locally

resource "local_file" "bastion_private_key" {
  content         = tls_private_key.bastion_key.private_key_pem
  filename        = var.bastion_private_key_filename
  file_permission = var.bastion_private_key_file_permission
}

# Security Group for Bastion

resource "aws_security_group" "bastion_sg" {
  name   = var.bastion_security_group_name
  vpc_id = module.vpc.vpc_id

  ingress {
    description = var.bastion_ingress_description
    from_port   = var.bastion_ingress_from_port
    to_port     = var.bastion_ingress_to_port
    protocol    = var.bastion_ingress_protocol
    cidr_blocks = ["${chomp(data.http.my_ip.response_body)}/32"]
  }


  egress {
    from_port   = var.default_egress_from_port
    to_port     = var.default_egress_to_port
    protocol    = var.default_egress_protocol
    cidr_blocks = var.default_egress_cidr_blocks
  }

  tags = {
    Name = var.bastion_security_group_name
  }
}


# Bastion Host

resource "aws_instance" "bastion_host" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.bastion_instance_type
  key_name                    = aws_key_pair.bastion_keypair.key_name
  monitoring                  = var.bastion_monitoring
  subnet_id                   = element(module.vpc.public_subnets, var.bastion_public_subnet_index)
  vpc_security_group_ids      = [aws_security_group.bastion_sg.id]
  associate_public_ip_address = var.bastion_associate_public_ip_address

  tags = merge(
    var.common_tags,
    var.bastion_tags,
    {
      Name = var.bastion_name
    }
  )
}
