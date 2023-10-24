#!/usr/bin/env python3
import logging
import queue
import threading


class Plugin(threading.Thread):
    """
    Base class for plugins that process incoming/outgoing data from connections
    with other plugins, forming a pipeline or graph.  Plugins can run either
    single-threaded or in an independent thread that processes data out of a queue.

    Frequent categories of plugins:
    
      * sources:  text prompts, images/video
      * llm_queries, RAG, dynamic LLM calls, image postprocessors
      * outputs:  print to stdout, save images/video
      
    Parameters:
    
      input_channels (int) -- 
      relay (bool) -- if true, will relay any inputs as outputs after processing
      threaded (bool) -- if true, will process queue from independent thread
    """
    def __init__(self, output_channels=1, relay=False, threaded=True, **kwargs):
        """
        Initialize plugin
        """
        super().__init__(daemon=True)

        self.relay = relay
        self.threaded = threaded
        
        self.outputs = [[] for i in range(output_channels)]
        self.output_channels = output_channels
        
        if threaded:
            self.input_queue = queue.Queue()
            self.input_event = threading.Event()
            #self.thread = threading.Thread(target=self._run, daemon=True)
            #self.thread.start()
        
    def process(self, input, **kwargs):
        """
        Abstract process() function that plugin instances should implement.
        Don't call this function externally unless threaded=False, because
        otherwise the plugin's internal thread dispatches from the queue.
        
        Plugins should return their output data (or None if there isn't any)
        You can also call self.output() directly as opposed to returning it.
        
        kwargs:
        
          sender (Plugin) -- only present if data sent from previous plugin
        """
        raise NotImplementedError(f"plugin {type(self)} has not implemented process()")
    
    def add(self, plugin, channel=0):
        """
        Connect this plugin with another, as either an input or an output.
        By default, this plugin will output to the specified plugin instance.
        
        Parameters:
        
          plugin (Plugin|callable) -- either the plugin to link to, or a callback
          
          mode (str) -- 'input' if this plugin should recieve data from the other
                        plugin, or 'output' if this plugin should send data to it.
                        
        Returns a reference to this plugin instance (self)
        """
        if not isinstance(plugin, Plugin):
            if not callable(plugin):
                raise TypeError(f"{type(self)}.add() expects either a Plugin instance or a callable function (was {type(plugin)})")
            from local_llm.plugins import Callback
            plugin = Callback(plugin)
            
        self.outputs[channel].append(plugin)
        logging.debug(f"connected plugins {type(self)} -> {type(plugin)}  (channel={channel})")
        return self
    
    def find(self, type):
        """
        Return the plugin with the specified type by searching for it among
        the pipeline graph of inputs and output connections to other plugins.
        """
        if isinstance(self, type):
            return self
            
        for output_channel in self.outputs:
            for output in output_channel:
                if isinstance(output, type):
                    return output
                plugin = output.find(type)
                if plugin is not None:
                    return plugin
            
        return None
    
    '''
    def __getitem__(self, type):
        """
        Subscript indexing [] operator alias for find()
        """
        return self.find(type)
    '''
    
    def __call__(self, input):
        """
        Callable () operator alias for the input() function
        """
        self.input(input, channel)
        
    def input(self, input):
        """
        Add data to the plugin's processing queue (or if threaded=False, process it now)
        TODO:  multiple input channels?
        """
        if self.threaded:
            self.input_queue.put(input)
            self.input_event.set()
        else:
            self.update()
            
    def output(self, output, channel=0):
        """
        Output data to the next plugin(s) on the specified channel (-1 for all channels)
        """
        if output is None:
            return
            
        if channel >= 0:
            for output_plugin in self.outputs[channel]:
                output_plugin.input(output)
        else:
            for output_channel in self.outputs:
                for output_plugin in output_channel:
                    output_plugin.input(output)
    
    def update(self):
        """
        Process all items in the queue (use this if created with threaded=False)
        """
        while not self.input_queue.empty():
            input = self.input_queue.get()
            self.output(self.process(input))
            if self.relay:
                self.output(input)
     
    def start(self):
        """
        Start threads for all plugins in the graph that have threading enabled.
        """
        if self.threaded:
            if not self.is_alive():
                super().start()
            
        for output_channel in self.outputs:
            for output in output_channel:
                output.start()
                
        return self
            
    def run(self):
        """
        @internal processes the queue forever when created with threaded=True
        """
        while True:
            self.input_event.wait()
            self.input_event.clear()
            self.update()
            