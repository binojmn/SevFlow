aws_region = "us-east-1"

vpc_name = "test-vpc-01"
vpc_cidr = "10.0.0.0/16"

azs = ["us-east-1a", "us-east-1b", "us-east-1c"]
private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

enable_nat_gateway      = true
enable_vpn_gateway      = false
single_nat_gateway      = true
map_public_ip_on_launch = true

common_tags = {
  Terraform   = "true"
  Environment = "dev"
}

public_subnet_tags = {
  "kubernetes.io/role/elb" = "1"
}

private_subnet_tags = {
  "kubernetes.io/role/internal-elb" = "1"
}

additional_eks_security_group_name = "additional-eks-sg"
eks_ingress_description            = "HTTPS from bastion host"
eks_ingress_from_port              = 443
eks_ingress_to_port                = 443
eks_ingress_protocol               = "tcp"

default_egress_from_port   = 0
default_egress_to_port     = 0
default_egress_protocol    = "-1"
default_egress_cidr_blocks = ["0.0.0.0/0"]

cluster_name       = "terraform-cluster"
kubernetes_version = "1.34"

eks_addons = {
  coredns = {}
  eks-pod-identity-agent = {
    before_compute = true
  }
  kube-proxy = {}
  vpc-cni = {
    before_compute = true
  }
}

endpoint_public_access                    = false
enable_cluster_creator_admin_permissions = true

node_group_ami_type       = "AL2023_x86_64_STANDARD"
node_group_instance_types = ["t3.small"]
node_group_use_latest_ami_release_version = true
node_group_ami_release_version            = ""
node_group_min_size       = 5
node_group_max_size       = 5
node_group_desired_size   = 5

bastion_key_algorithm               = "RSA"
bastion_key_rsa_bits                = 4096
bastion_key_name                    = "bastion-key"
bastion_private_key_filename        = "bastion-key.pem"
bastion_private_key_file_permission = "0400"

bastion_security_group_name = "bastion-sg"
bastion_ingress_description = "SSH from my IP"
bastion_ingress_from_port   = 22
bastion_ingress_to_port     = 22
bastion_ingress_protocol    = "tcp"

bastion_name                        = "bastion-host"
bastion_instance_type               = "t3.micro"
bastion_monitoring                  = true
bastion_public_subnet_index         = 0
bastion_associate_public_ip_address = true

bastion_tags = {
  Role = "bastion"
}

my_ip_lookup_url                = "https://checkip.amazonaws.com"
bastion_ami_most_recent         = true
bastion_ami_name_filter         = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
bastion_ami_virtualization_type = "hvm"
bastion_ami_owners              = ["099720109477"]
