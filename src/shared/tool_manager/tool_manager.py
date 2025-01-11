#!/usr/bin/env python3
import boto3
import click
import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from src.utils.bedrock_agent import Toolbox


@click.group()
@click.option('--table-name', required=False, default='bedrock_agent_tools', help='DynamoDB table name')
@click.option('--region', default='us-west-2', help='AWS region')
def cli(table_name, region):
    """Tool Manager - manages lambda tools for use with (potentially many) Bedrock Agents"""
    # Create the toolbox instance
    toolbox = Toolbox(table_name=table_name)
    # Store it in the context
    ctx = click.get_current_context()
    ctx.obj = {'toolbox': toolbox}
    # If region isn't specified, get the current region from boto3
    if region is None:
        region = boto3.Session().region_name
    ctx.obj['toolbox'].region = region
    ctx.obj['toolbox'].account = boto3.client("sts").get_caller_identity()["Account"]


@cli.command()
@click.pass_context
def create_table(ctx):
    """Create DynamoDB table for storing tool registration (default: bedrock_agent_tools)"""
    ctx.obj['toolbox'].create_table()
    click.echo(f"Table created successfully")


@cli.command()
@click.pass_context
def delete_table(ctx):
    """Delete DynamoDB table for tools"""
    ctx.obj['toolbox'].delete_table()
    click.echo(f"Table deleted successfully")


@cli.command()
@click.argument('source', type=click.Path(exists=True))
@click.pass_context
def register(ctx, source):
    """Register tools from a source definition file"""
    try:
        with open(source) as f:
            tool_source = json.load(f)

        # Validate required fields
        if 'code' not in tool_source:
            raise ValueError("Source file must contain 'code' field")
        if 'definition' not in tool_source or not isinstance(tool_source['definition'], list):
            raise ValueError("Source file must contain 'definition' field as a list")

        # For each tool definition in the source file
        for tool_def in tool_source['definition']:
            if 'name' not in tool_def:
                raise ValueError("Each tool definition must contain a 'name' field")

            # replace {region} and {account} in the code field
            tool_source['code'] = tool_source['code'].replace('{region}', ctx.obj['toolbox'].region)
            tool_source['code'] = tool_source['code'].replace('{account_id}', ctx.obj['toolbox'].account)

            # Register individual tool
            ctx.obj['toolbox'].register_tool(
                tool_name=tool_def['name'],
                tool_code_or_arn=tool_source['code'],
                tool_definition=tool_def.get('parameters', ''),
                description=tool_def.get('description', '')
            )
            click.echo(f"Tool '{tool_def['name']}' registered successfully")

    except json.JSONDecodeError as e:
        click.echo(f"Error parsing source file: {str(e)}", err=True)
    except ValueError as e:
        click.echo(f"Invalid source file format: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"Error registering tools: {str(e)}", err=True)


@cli.command()
@click.pass_context
def list_tools(ctx):
    """List all registered tools"""
    tools = ctx.obj['toolbox'].list_tools()
    for tool in tools:
        click.echo(f"\nTool: {tool['tool_name']}")
        click.echo(f"Description: {tool['description']}")
        click.echo(f"Code: {tool['tool_code']}")


@cli.command()
@click.argument('name')
@click.pass_context
def unregister(ctx, name):
    """Unregister a specific tool"""
    # Check if the tool exists
    tool = ctx.obj['toolbox'].get_tool(name)
    if not tool:
        click.echo(f"Tool '{name}' not found")
        return
    # Delete the tool from the Toolbox
    ctx.obj['toolbox'].unregister_tool(name)
    print(f"Tool {name} unregistered from toolbox")


@cli.command()
@click.argument('name')
@click.pass_context
def get(ctx, name):
    """Get details for a specific tool"""
    tool = ctx.obj['toolbox'].get_tool(name)
    if tool:
        click.echo(json.dumps(tool, indent=2))
    else:
        click.echo(f"Tool '{name}' not found")


def main():
    cli(obj={})


if __name__ == '__main__':
    main()
