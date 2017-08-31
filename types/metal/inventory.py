#!/usr/bin/env python

# The inventory script would track the mysql db hosted stock table for this
# machine type, and when specific counts drop below threashold, would send
# requets on the queue for new machines to be provisioned. In case of 
# static backing stock, as in the case of the bare metal machines, its 
# upto the inventory script to identify specific hosts to be installed, 
# not the provision script ( which just executes the reqest )