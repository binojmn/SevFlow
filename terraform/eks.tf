resource "aws_security_group" "add_sg_eks" {
  name   = var.additional_eks_security_group_name
  vpc_id = module.vpc.vpc_id
  ingress {
    description     = var.eks_ingress_description
    from_port       = var.eks_ingress_from_port
    to_port         = var.eks_ingress_to_port
    protocol        = var.eks_ingress_protocol
    security_groups = [aws_security_group.bastion_sg.id]
  }


  egress {
    from_port   = var.default_egress_from_port
    to_port     = var.default_egress_to_port
    protocol    = var.default_egress_protocol
    cidr_blocks = var.default_egress_cidr_blocks
  }

  tags = {
    Name = var.additional_eks_security_group_name
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version

  addons = var.eks_addons

  # Optional
  endpoint_public_access = var.endpoint_public_access

  # Optional: Adds the current caller identity as an administrator via cluster access entry
  enable_cluster_creator_admin_permissions = var.enable_cluster_creator_admin_permissions


  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  additional_security_group_ids = [aws_security_group.add_sg_eks.id]

  eks_managed_node_groups = {
    example = {
      # Starting on 1.30, AL2023 is the default AMI type for EKS managed node groups
      ami_type                        = var.node_group_ami_type
      instance_types                  = var.node_group_instance_types
      use_latest_ami_release_version  = var.node_group_use_latest_ami_release_version
      ami_release_version             = var.node_group_ami_release_version

      min_size     = var.node_group_min_size
      max_size     = var.node_group_max_size
      desired_size = var.node_group_desired_size
    }
  }

  tags = var.common_tags
}
