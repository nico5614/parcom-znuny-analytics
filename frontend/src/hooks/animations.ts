import { createContext, useContext } from 'react'
export const AnimationContext = createContext(true)
export const useAnimations = () => useContext(AnimationContext)
