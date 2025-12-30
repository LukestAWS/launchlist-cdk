#!/usr/bin/env python3
import aws_cdk as cdk

from launchlist.launchlist_stack import LaunchlistStack

app = cdk.App()
LaunchlistStack(app, "LaunchlistStack")

app.synth()
