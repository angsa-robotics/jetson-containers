from jetson_containers import update_dependencies
from packaging.version import Version
from ..tensorflow.version import TENSORFLOW_VERSION

def tensorflow_addons(version, tensorflow=None, requires=None):
    pkg = package.copy()
    
    pkg['name'] = f"tensorflow_addons:{version.split('-')[0]}"  # remove any -rc* suffix
    
    if tensorflow:
        pkg['depends'] = update_dependencies(pkg['depends'], f"tensorflow2:{tensorflow}")
    else:
        tensorflow = TENSORFLOW_VERSION  
        
    if requires:
        pkg['requires'] = requires
   
    if len(version.split('.')) < 3:
        version = version + '.0'
        
    pkg['build_args'] = {
        'TENSORFLOW_ADDONS_VERSION': version,
    }
    
    builder = pkg.copy()
    builder['name'] = builder['name'] + '-builder'
    builder['build_args'] = {**builder['build_args'], 'FORCE_BUILD': 'on'}
    
    if not isinstance(tensorflow, Version):
        tensorflow = Version(tensorflow)

    if tensorflow == TENSORFLOW_VERSION:
        pkg['alias'] = 'tensorflow_addons'
        builder['alias'] = 'tensorflow_addons:builder'

    return pkg, builder
    
 
package = [
    # JetPack 5/6
    tensorflow_addons('2.18.0', tensorflow='2.18.0', requires='==36.*'),
]
