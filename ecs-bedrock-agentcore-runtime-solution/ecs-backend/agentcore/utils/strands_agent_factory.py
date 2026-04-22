"""
Strands Agent Factory - Creates and configures Strands agents for AgentCore integration.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from agentcore.models.strands_models import (
    StrandsAgent,
    StrandsAgentType,
    StrandsAgentStatus,
    StrandsRuntimeType,
    StrandsAgentCapability,
    create_wa_security_agent,
    create_cost_optimization_agent,
    create_aws_api_agent
)

logger = logging.getLogger(__name__)


class StrandsAgentFactory:
    """Factory for creating and configuring Strands agents."""
    
    def __init__(self, parameter_prefix: str = "coa"):
        """
        Initialize the Strands agent factory.
        
        Args:
            parameter_prefix: Parameter prefix for agent configuration
        """
        self.parameter_prefix = parameter_prefix
        self.agent_templates = self._load_agent_templates()
    
    def create_agent_from_config(
        self,
        agent_config: Dict[str, Any],
        agent_id: Optional[str] = None
    ) -> StrandsAgent:
        """
        Create a Strands agent from configuration.
        
        Args:
            agent_config: Agent configuration dictionary
            agent_id: Optional agent ID override
            
        Returns:
            Configured StrandsAgent instance
        """
        agent_type_str = agent_config.get("agent_type", "general_purpose_agent")
        agent_type = StrandsAgentType(agent_type_str)
        
        # Generate agent ID if not provided
        if not agent_id:
            agent_id = self._generate_agent_id(agent_type)
        
        agent_name = agent_config.get("agent_name", f"{agent_type.value}_{agent_id}")
        agent_arn = agent_config.get("agent_arn", f"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{agent_id}")
        
        # Use factory functions for known agent types
        if agent_type == StrandsAgentType.WA_SECURITY:
            agent = create_wa_security_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                endpoint_url=agent_config.get("endpoint_url")
            )
        elif agent_type == StrandsAgentType.COST_OPTIMIZATION:
            agent = create_cost_optimization_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                endpoint_url=agent_config.get("endpoint_url")
            )
        elif agent_type == StrandsAgentType.AWS_API:
            agent = create_aws_api_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                endpoint_url=agent_config.get("endpoint_url")
            )
        else:
            # Create generic agent
            agent = self._create_generic_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                agent_config=agent_config
            )
        
        # Apply additional configuration
        self._apply_agent_config(agent, agent_config)
        
        logger.info(f"Created Strands agent: {agent.agent_name} ({agent.agent_type.value})")
        return agent
    
    def create_agent_from_template(
        self,
        template_name: str,
        agent_id: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> StrandsAgent:
        """
        Create a Strands agent from a predefined template.
        
        Args:
            template_name: Name of the agent template
            agent_id: Optional agent ID override
            overrides: Optional configuration overrides
            
        Returns:
            Configured StrandsAgent instance
        """
        if template_name not in self.agent_templates:
            raise ValueError(f"Unknown agent template: {template_name}")
        
        template_config = self.agent_templates[template_name].copy()
        
        # Apply overrides
        if overrides:
            template_config.update(overrides)
        
        return self.create_agent_from_config(template_config, agent_id)
    
    def create_multi_capability_agent(
        self,
        agent_id: str,
        agent_name: str,
        capabilities: List[StrandsAgentCapability],
        agent_arn: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StrandsAgent:
        """
        Create a Strands agent with multiple capabilities.
        
        Args:
            agent_id: Agent ID
            agent_name: Agent name
            capabilities: List of agent capabilities
            agent_arn: Optional agent ARN
            metadata: Optional metadata
            
        Returns:
            Configured StrandsAgent instance
        """
        if not agent_arn:
            agent_arn = f"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{agent_id}"
        
        # Determine agent type based on capabilities
        agent_type = self._determine_agent_type_from_capabilities(capabilities)
        
        agent = StrandsAgent(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_arn=agent_arn,
            agent_type=agent_type,
            capabilities=capabilities,
            metadata=metadata or {}
        )
        
        # Set supported domains and services based on capabilities
        self._configure_agent_from_capabilities(agent)
        
        logger.info(f"Created multi-capability Strands agent: {agent_name} with {len(capabilities)} capabilities")
        return agent
    
    def clone_agent(
        self,
        source_agent: StrandsAgent,
        new_agent_id: str,
        new_agent_name: Optional[str] = None,
        modifications: Optional[Dict[str, Any]] = None
    ) -> StrandsAgent:
        """
        Clone an existing Strands agent with modifications.
        
        Args:
            source_agent: Source agent to clone
            new_agent_id: New agent ID
            new_agent_name: Optional new agent name
            modifications: Optional modifications to apply
            
        Returns:
            Cloned and modified StrandsAgent instance
        """
        if not new_agent_name:
            new_agent_name = f"{source_agent.agent_name}_clone"
        
        # Create new agent with copied attributes
        cloned_agent = StrandsAgent(
            agent_id=new_agent_id,
            agent_name=new_agent_name,
            agent_arn=f"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{new_agent_id}",
            agent_type=source_agent.agent_type,
            runtime_type=source_agent.runtime_type,
            status=StrandsAgentStatus.DISCOVERED,  # Reset status
            capabilities=source_agent.capabilities.copy(),
            metadata=source_agent.metadata.copy(),
            framework=source_agent.framework,
            model_id=source_agent.model_id,
            supported_domains=source_agent.supported_domains.copy(),
            supported_aws_services=source_agent.supported_aws_services.copy()
        )
        
        # Apply modifications
        if modifications:
            self._apply_agent_config(cloned_agent, modifications)
        
        logger.info(f"Cloned Strands agent: {new_agent_name} from {source_agent.agent_name}")
        return cloned_agent
    
    def _generate_agent_id(self, agent_type: StrandsAgentType) -> str:
        """
        Generate a unique agent ID.
        
        Args:
            agent_type: Type of agent
            
        Returns:
            Generated agent ID
        """
        import uuid
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{agent_type.value}_{timestamp}_{short_uuid}"
    
    def _create_generic_agent(
        self,
        agent_id: str,
        agent_name: str,
        agent_arn: str,
        agent_config: Dict[str, Any]
    ) -> StrandsAgent:
        """
        Create a generic Strands agent.
        
        Args:
            agent_id: Agent ID
            agent_name: Agent name
            agent_arn: Agent ARN
            agent_config: Agent configuration
            
        Returns:
            Generic StrandsAgent instance
        """
        capabilities = []
        
        # Create capabilities from config
        capability_configs = agent_config.get("capabilities", [])
        for cap_config in capability_configs:
            capability = StrandsAgentCapability(
                name=cap_config.get("name", "general_capability"),
                description=cap_config.get("description", "General purpose capability"),
                aws_services=cap_config.get("aws_services", []),
                domains=cap_config.get("domains", ["general"]),
                keywords=cap_config.get("keywords", []),
                confidence_level=cap_config.get("confidence_level", 1.0)
            )
            capabilities.append(capability)
        
        agent = StrandsAgent(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_arn=agent_arn,
            agent_type=StrandsAgentType.GENERAL_PURPOSE,
            capabilities=capabilities,
            endpoint_url=agent_config.get("endpoint_url"),
            supported_domains=agent_config.get("supported_domains", ["general"]),
            supported_aws_services=agent_config.get("supported_aws_services", [])
        )
        
        return agent
    
    def _apply_agent_config(
        self,
        agent: StrandsAgent,
        config: Dict[str, Any]
    ):
        """
        Apply configuration to an agent.
        
        Args:
            agent: Agent to configure
            config: Configuration to apply
        """
        # Update metadata
        if "metadata" in config:
            agent.metadata.update(config["metadata"])
        
        # Update model ID
        if "model_id" in config:
            agent.model_id = config["model_id"]
        
        # Update status
        if "status" in config:
            agent.status = StrandsAgentStatus(config["status"])
        
        # Update runtime type
        if "runtime_type" in config:
            agent.runtime_type = StrandsRuntimeType(config["runtime_type"])
        
        # Update health check URL
        if "health_check_url" in config:
            agent.health_check_url = config["health_check_url"]
        
        # Update supported domains and services
        if "supported_domains" in config:
            agent.supported_domains = config["supported_domains"]
        
        if "supported_aws_services" in config:
            agent.supported_aws_services = config["supported_aws_services"]
    
    def _determine_agent_type_from_capabilities(
        self,
        capabilities: List[StrandsAgentCapability]
    ) -> StrandsAgentType:
        """
        Determine agent type based on capabilities.
        
        Args:
            capabilities: List of capabilities
            
        Returns:
            Determined agent type
        """
        # Check for security-related capabilities
        security_keywords = ["security", "compliance", "vulnerability", "threat"]
        if any(
            any(keyword in cap.keywords for keyword in security_keywords)
            for cap in capabilities
        ):
            return StrandsAgentType.WA_SECURITY
        
        # Check for cost-related capabilities
        cost_keywords = ["cost", "billing", "optimization", "savings"]
        if any(
            any(keyword in cap.keywords for keyword in cost_keywords)
            for cap in capabilities
        ):
            return StrandsAgentType.COST_OPTIMIZATION
        
        # Check for API-related capabilities
        api_keywords = ["api", "list", "describe", "get", "create"]
        if any(
            any(keyword in cap.keywords for keyword in api_keywords)
            for cap in capabilities
        ):
            return StrandsAgentType.AWS_API
        
        return StrandsAgentType.GENERAL_PURPOSE
    
    def _configure_agent_from_capabilities(
        self,
        agent: StrandsAgent
    ):
        """
        Configure agent domains and services based on capabilities.
        
        Args:
            agent: Agent to configure
        """
        all_domains = set()
        all_services = set()
        
        for capability in agent.capabilities:
            all_domains.update(capability.domains)
            all_services.update(capability.aws_services)
        
        agent.supported_domains = list(all_domains)
        agent.supported_aws_services = list(all_services)
    
    def _load_agent_templates(self) -> Dict[str, Dict[str, Any]]:
        """
        Load predefined agent templates.
        
        Returns:
            Dictionary of agent templates
        """
        return {
            "wa_security": {
                "agent_type": "wa_security_agent",
                "agent_name": "Well-Architected Security Agent",
                "capabilities": [
                    {
                        "name": "security_assessment",
                        "description": "AWS security posture assessment",
                        "aws_services": ["guardduty", "inspector", "securityhub"],
                        "domains": ["security"],
                        "keywords": ["security", "vulnerability", "compliance"]
                    }
                ],
                "supported_domains": ["security", "compliance"],
                "supported_aws_services": ["guardduty", "inspector", "securityhub", "macie"]
            },
            "cost_optimization": {
                "agent_type": "cost_optimization_agent",
                "agent_name": "Cost Optimization Agent",
                "capabilities": [
                    {
                        "name": "cost_analysis",
                        "description": "AWS cost analysis and optimization",
                        "aws_services": ["ce", "budgets", "compute-optimizer"],
                        "domains": ["cost_optimization"],
                        "keywords": ["cost", "billing", "optimization"]
                    }
                ],
                "supported_domains": ["cost_optimization"],
                "supported_aws_services": ["ce", "budgets", "compute-optimizer"]
            },
            "aws_api": {
                "agent_type": "aws_api_agent",
                "agent_name": "AWS API Agent",
                "capabilities": [
                    {
                        "name": "aws_api_operations",
                        "description": "AWS API operations and resource management",
                        "aws_services": ["*"],
                        "domains": ["general"],
                        "keywords": ["list", "describe", "get", "api"]
                    }
                ],
                "supported_domains": ["general", "operations"],
                "supported_aws_services": ["*"]
            }
        }
    
    def get_available_templates(self) -> List[str]:
        """
        Get list of available agent templates.
        
        Returns:
            List of template names
        """
        return list(self.agent_templates.keys())
    
    def validate_agent_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate agent configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Required fields
        required_fields = ["agent_type"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Validate agent type
        if "agent_type" in config:
            try:
                StrandsAgentType(config["agent_type"])
            except ValueError:
                errors.append(f"Invalid agent_type: {config['agent_type']}")
        
        # Validate capabilities
        if "capabilities" in config:
            if not isinstance(config["capabilities"], list):
                errors.append("capabilities must be a list")
            elif len(config["capabilities"]) == 0:
                warnings.append("Agent has no capabilities defined")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


# Convenience functions

def create_strands_agent_factory(parameter_prefix: str = "coa") -> StrandsAgentFactory:
    """
    Create a Strands agent factory instance.
    
    Args:
        parameter_prefix: Parameter prefix for agent configuration
        
    Returns:
        StrandsAgentFactory instance
    """
    return StrandsAgentFactory(parameter_prefix)


def create_agent_from_ssm_config(
    ssm_parameter_path: str,
    region: str = "us-east-1",
    parameter_prefix: str = "coa"
) -> Optional[StrandsAgent]:
    """
    Create a Strands agent from SSM parameter configuration.
    
    Args:
        ssm_parameter_path: SSM parameter path containing agent config
        region: AWS region
        parameter_prefix: Parameter prefix
        
    Returns:
        StrandsAgent instance or None if creation fails
    """
    try:
        import boto3
        import json
        
        ssm_client = boto3.client("ssm", region_name=region)
        response = ssm_client.get_parameter(Name=ssm_parameter_path)
        
        config = json.loads(response["Parameter"]["Value"])
        
        factory = StrandsAgentFactory(parameter_prefix)
        return factory.create_agent_from_config(config)
        
    except Exception as e:
        logger.error(f"Failed to create agent from SSM config {ssm_parameter_path}: {e}")
        return None