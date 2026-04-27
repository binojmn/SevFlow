variable "aws_region" {
  type = string
}

variable "vpc_name" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "azs" {
  type = list(string)
}

variable "private_subnets" {
  type = list(string)
}

variable "public_subnets" {
  type = list(string)
}

variable "enable_nat_gateway" {
  type = bool
}

variable "enable_vpn_gateway" {
  type = bool
}

variable "single_nat_gateway" {
  type = bool
}

variable "map_public_ip_on_launch" {
  type = bool
}

variable "common_tags" {
  type = map(string)
}

variable "public_subnet_tags" {
  type = map(string)
}

variable "private_subnet_tags" {
  type = map(string)
}

variable "additional_eks_security_group_name" {
  type = string
}

variable "eks_ingress_description" {
  type = string
}

variable "eks_ingress_from_port" {
  type = number
}

variable "eks_ingress_to_port" {
  type = number
}

variable "eks_ingress_protocol" {
  type = string
}

variable "default_egress_from_port" {
  type = number
}

variable "default_egress_to_port" {
  type = number
}

variable "default_egress_protocol" {
  type = string
}

variable "default_egress_cidr_blocks" {
  type = list(string)
}

variable "cluster_name" {
  type = string
}

variable "kubernetes_version" {
  type = string
}

variable "eks_addons" {
  type = map(any)
}

variable "endpoint_public_access" {
  type = bool
}

variable "enable_cluster_creator_admin_permissions" {
  type = bool
}

variable "node_group_ami_type" {
  type = string
}

variable "node_group_instance_types" {
  type = list(string)
}

variable "node_group_min_size" {
  type = number
}

variable "node_group_max_size" {
  type = number
}

variable "node_group_desired_size" {
  type = number
}

variable "node_group_use_latest_ami_release_version" {
  type = bool
}

variable "node_group_ami_release_version" {
  type = string
}

variable "bastion_key_algorithm" {
  type = string
}

variable "bastion_key_rsa_bits" {
  type = number
}

variable "bastion_key_name" {
  type = string
}

variable "bastion_private_key_filename" {
  type = string
}

variable "bastion_private_key_file_permission" {
  type = string
}

variable "bastion_security_group_name" {
  type = string
}

variable "bastion_ingress_description" {
  type = string
}

variable "bastion_ingress_from_port" {
  type = number
}

variable "bastion_ingress_to_port" {
  type = number
}

variable "bastion_ingress_protocol" {
  type = string
}

variable "bastion_name" {
  type = string
}

variable "bastion_instance_type" {
  type = string
}

variable "bastion_ami_most_recent" {
  type = bool
}

variable "bastion_ami_name_filter" {
  type = string
}

variable "bastion_ami_virtualization_type" {
  type = string
}

variable "bastion_ami_owners" {
  type = list(string)
}

variable "bastion_monitoring" {
  type = bool
}

variable "bastion_public_subnet_index" {
  type = number
}

variable "bastion_associate_public_ip_address" {
  type = bool
}

variable "bastion_tags" {
  type = map(string)
}

variable "my_ip_lookup_url" {
  type = string
}
